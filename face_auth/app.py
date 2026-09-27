"""Local, consent-based face sign-in prototype.

Do not deploy this as a government production authentication system.  Use a
reviewed identity provider, liveness detection, encryption at rest, an access
log, retention policy, and a non-biometric recovery path before production.
"""
from __future__ import annotations

import base64
import os
import secrets
import sqlite3
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import cv2
import numpy as np
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for

BASE_DIR = Path(__file__).resolve().parent
EXPLORE_DIR = BASE_DIR.parent / "ecora" / "frontend"
DATA_DIR = BASE_DIR / "data"
FACES_DIR = DATA_DIR / "faces"
DATABASE = DATA_DIR / "employees.db"
MODEL = DATA_DIR / "face_model.yml"
CASCADE = BASE_DIR / "haarcascade_frontalface_default.xml"
MAX_IMAGE_BYTES = 2_500_000
# LBPH is only a local prototype recognizer.  A low threshold deliberately
# favours false rejects over the much more serious false accepts.
# This remains below the original 58 threshold, while allowing normal webcam
# lighting differences after a straight-on enrollment.
MATCH_THRESHOLD = 48.0  # LBPH: lower distance means a closer match.
VERIFICATION_FRAMES = 3

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("FACE_AUTH_SECRET_KEY", secrets.token_urlsafe(32)),
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


def db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialise():
    DATA_DIR.mkdir(exist_ok=True)
    FACES_DIR.mkdir(exist_ok=True)
    with db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                official_id TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                designation TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def detector():
    cascade = cv2.CascadeClassifier(str(CASCADE))
    if cascade.empty():
        raise RuntimeError("The face detector could not be loaded.")
    return cascade


def image_from_data_url(value: str):
    if not isinstance(value, str) or "," not in value:
        raise ValueError("Invalid camera image.")
    raw = base64.b64decode(value.split(",", 1)[1], validate=True)
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Camera image is too large.")
    frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Camera image could not be read.")
    return frame


def crop_single_face(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = detector().detectMultiScale(gray, scaleFactor=1.15, minNeighbors=6, minSize=(80, 80))
    if len(faces) == 0:
        raise ValueError("No face detected. Centre your face and try again.")
    if len(faces) != 1:
        raise ValueError("Only one face may be visible during authentication.")
    x, y, width, height = faces[0]
    face = cv2.resize(gray[y:y + height, x:x + width], (160, 160))
    # Webcam lighting often differs substantially between enrollment and
    # sign-in. Histogram normalization makes LBPH compare facial texture,
    # rather than a room's brightness or camera exposure.
    return cv2.equalizeHist(face)


def rebuild_model():
    samples, labels = [], []
    for employee_dir in FACES_DIR.iterdir():
        if not employee_dir.is_dir() or not employee_dir.name.isdigit():
            continue
        for sample in employee_dir.glob("*.png"):
            face = cv2.imread(str(sample), cv2.IMREAD_GRAYSCALE)
            if face is not None:
                samples.append(cv2.equalizeHist(cv2.resize(face, (160, 160))))
                labels.append(int(employee_dir.name))
    if not samples:
        if MODEL.exists():
            MODEL.unlink()
        return
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(samples, np.array(labels, dtype=np.int32))
    recognizer.save(str(MODEL))


initialise()


FRONTEND_PAGES = frozenset({
    "index.html",
    "watershed.html",
    "geo-images.html",
    "report.html",
    "report-status.html",
    "chatbot.html",
})


@app.get("/")
@app.get("/explore.html")
def explore_landing():
    """Public Ecora landing page."""
    return send_from_directory(BASE_DIR.parent, "explore.html")


def authenticated_employee():
    employee_id = session.get("employee_id")
    if not employee_id:
        return None
    with db() as connection:
        return connection.execute("SELECT id FROM employees WHERE id = ?", (employee_id,)).fetchone()


@app.get("/dashboard/")
def dashboard_index():
    """Public entry point for the Ecora dashboard."""
    return send_from_directory(EXPLORE_DIR, "index.html")


@app.get("/dashboard/assets/<path:filename>")
def dashboard_asset(filename: str):
    """Shared CSS and JavaScript used by the dashboard pages."""
    return send_from_directory(EXPLORE_DIR / "assets", filename)


@app.get("/dashboard/<page>")
def dashboard_page(page: str):
    """Serve only the known dashboard pages; never expose arbitrary files."""
    if page not in FRONTEND_PAGES:
        return "Not found", 404
    return send_from_directory(EXPLORE_DIR, page)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    payload = request.get_json(silent=True) or {}
    official_id = str(payload.get("officialId", "")).strip().upper()
    full_name = " ".join(str(payload.get("fullName", "")).split())
    designation = " ".join(str(payload.get("designation", "")).split())
    images = payload.get("images", [])
    if not (3 <= len(images) <= 8):
        return jsonify(success=False, message="Capture 3 to 8 face samples before registering."), 400
    if not official_id or len(official_id) > 50 or not full_name or len(full_name) > 120 or not designation or len(designation) > 120:
        return jsonify(success=False, message="Enter a valid official ID, full name, and designation."), 400
    try:
        crops = [crop_single_face(image_from_data_url(image)) for image in images]
        with db() as connection:
            cursor = connection.execute(
                "INSERT INTO employees (official_id, full_name, designation) VALUES (?, ?, ?)",
                (official_id, full_name, designation),
            )
            employee_id = cursor.lastrowid
        employee_dir = FACES_DIR / str(employee_id)
        employee_dir.mkdir()
        for index, crop in enumerate(crops):
            cv2.imwrite(str(employee_dir / f"{index}.png"), crop)
        rebuild_model()
        return jsonify(success=True, message="Registration complete. You can now sign in with your face.", redirect=url_for("login"))
    except sqlite3.IntegrityError:
        return jsonify(success=False, message="That official ID is already registered."), 409
    except (ValueError, RuntimeError) as error:
        return jsonify(success=False, message=str(error)), 400


@app.get("/location-selection")
def location_selection():
    """Choose a demo jurisdiction after first-time registration."""
    return render_template("location_selection.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if authenticated_employee() is not None:
            return redirect(url_for("dashboard"))
        return render_template("login.html")
    if not MODEL.exists():
        return jsonify(success=False, message="No registered faces are available yet."), 400
    try:
        images = (request.get_json(silent=True) or {}).get("images", [])
        if not isinstance(images, list) or len(images) != VERIFICATION_FRAMES:
            raise ValueError(f"Provide exactly {VERIFICATION_FRAMES} verification frames.")
        faces = [crop_single_face(image_from_data_url(image)) for image in images]
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(str(MODEL))
        predictions = [recognizer.predict(face) for face in faces]
        employee_ids = {employee_id for employee_id, _ in predictions}
        distances = [distance for _, distance in predictions]
        if len(employee_ids) != 1 or any(distance > MATCH_THRESHOLD for distance in distances):
            return jsonify(success=False, message="Face not recognized. Please try again or use your approved recovery process."), 401
        employee_id = predictions[0][0]
        with db() as connection:
            employee = connection.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
        if employee is None:
            return jsonify(success=False, message="Face record is no longer active."), 401
        session.clear()
        session.permanent = True
        session["employee_id"] = employee["id"]
        return jsonify(success=True, message="Login successful.", redirect=url_for("location_selection"))
    except (ValueError, RuntimeError) as error:
        return jsonify(success=False, message=str(error)), 400


@app.get("/dashboard")
def dashboard():
    if authenticated_employee() is None:
        session.clear()
        return redirect(url_for("login"))
    return redirect(url_for("dashboard_index"))


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return_to = request.args.get("return_to", "")
    parsed = urlparse(return_to)
    allowed_origins = {
        "http://127.0.0.1:5000", "http://localhost:5000",
        "http://127.0.0.1:5500", "http://localhost:5500",
    }
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin in allowed_origins and parsed.path in {"/", "/explore.html"}:
        return redirect(return_to)
    return redirect(url_for("explore_landing"))


if __name__ == "__main__":
    app.run(debug=True)
