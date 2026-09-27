"""
Ecora backend - FastAPI
All data below is DUMMY data for prototyping. Replace with real
sensor / survey / GIS data sources later.
"""
import random
import sqlite3
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Ecora API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
DATABASE = Path(__file__).parent / "ecora.db"


def db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialise_database():
    """Create the persistent report store on first startup."""
    with db_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                image_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)


initialise_database()


# ---------------------------------------------------------------------
# 1. LAND / MAP PAGE
# ---------------------------------------------------------------------

def classify_village_level(agri_pct: float, rainfall_mm: float) -> str:
    """
    Simple rule engine (placeholder logic, tune later):
      - Rainfall low (<600mm/yr) -> Low level land
      - Agriculture share high (>=60%) AND rainfall not low -> High level land
      - Everything else -> Moderate level land
    """
    if rainfall_mm < 600:
        return "Low"
    if agri_pct >= 60:
        return "High"
    return "Moderate"


VILLAGE_LAND = {
    "village": "Hosahalli",
    "total_acres": 1240,
    # dummy polygon zones for the SVG land map (percent coordinates 0-100)
    "zones": [
        {"id": "z1", "type": "agriculture", "label": "North Fields",
         "points": "5,10 40,8 42,35 8,38"},
        {"id": "z2", "type": "agriculture", "label": "East Paddy",
         "points": "55,15 92,12 90,40 58,42"},
        {"id": "z3", "type": "non_agriculture", "label": "Village Core",
         "points": "40,45 65,44 66,70 42,72"},
        {"id": "z4", "type": "non_agriculture", "label": "Rocky Belt",
         "points": "10,55 35,52 33,85 8,88"},
        {"id": "z5", "type": "agriculture", "label": "South Fields",
         "points": "68,55 95,58 93,90 66,88"},
    ],
    "agriculture_acres": 780,
    "non_agriculture_acres": 460,
    "water_flowing_acres": 310,
    "water_not_flowing_acres": 930,
    "excess_water_acres": 45,  # water flowing more than necessary
    "annual_rainfall_mm": 710,
}

# City-specific dummy values used after a user chooses a service area. The
# shared map geometry remains illustrative, while all displayed land and water
# details are selected by the requested location.
LOCATION_PROFILES = {
    "bengaluru": {"village": "Bengaluru", "total_acres": 1860, "agriculture_acres": 620,
                   "non_agriculture_acres": 1240, "water_flowing_acres": 410,
                   "water_not_flowing_acres": 1450, "excess_water_acres": 68,
                   "annual_rainfall_mm": 970, "main_water_body": "Vrishabhavathi Valley"},
    "mysuru": {"village": "Mysuru", "total_acres": 1540, "agriculture_acres": 940,
                "non_agriculture_acres": 600, "water_flowing_acres": 520,
                "water_not_flowing_acres": 1020, "excess_water_acres": 31,
                "annual_rainfall_mm": 790, "main_water_body": "Kaveri Basin Channel"},
    "pune": {"village": "Pune", "total_acres": 1720, "agriculture_acres": 730,
             "non_agriculture_acres": 990, "water_flowing_acres": 360,
             "water_not_flowing_acres": 1360, "excess_water_acres": 56,
             "annual_rainfall_mm": 720, "main_water_body": "Mula-Mutha River"},
    "nashik": {"village": "Nashik", "total_acres": 1490, "agriculture_acres": 980,
               "non_agriculture_acres": 510, "water_flowing_acres": 470,
               "water_not_flowing_acres": 1020, "excess_water_acres": 27,
               "annual_rainfall_mm": 690, "main_water_body": "Godavari River"},
    "doddakere": {"village": "Doddakere", "total_acres": 1080, "agriculture_acres": 690,
                   "non_agriculture_acres": 390, "water_flowing_acres": 280,
                   "water_not_flowing_acres": 800, "excess_water_acres": 40,
                   "annual_rainfall_mm": 735, "main_water_body": "Doddakere Pond"},
    "kothanur": {"village": "Kothanur", "total_acres": 1160, "agriculture_acres": 720,
                  "non_agriculture_acres": 440, "water_flowing_acres": 295,
                  "water_not_flowing_acres": 865, "excess_water_acres": 34,
                  "annual_rainfall_mm": 805, "main_water_body": "Kothanur Lake"},
    "kumbharwadi": {"village": "Kumbharwadi", "total_acres": 1320, "agriculture_acres": 840,
                     "non_agriculture_acres": 480, "water_flowing_acres": 325,
                     "water_not_flowing_acres": 995, "excess_water_acres": 49,
                     "annual_rainfall_mm": 680, "main_water_body": "Bhama River Channel"},
}


def location_profile(location: Optional[str]):
    profile = deepcopy(VILLAGE_LAND)
    profile.update(LOCATION_PROFILES.get((location or "").strip().lower(), {}))
    return profile


@app.get("/api/land-overview")
def land_overview(location: Optional[str] = None):
    v = location_profile(location)
    agri_pct = round(v["agriculture_acres"] / v["total_acres"] * 100, 1)
    non_agri_pct = round(v["non_agriculture_acres"] / v["total_acres"] * 100, 1)
    level = classify_village_level(agri_pct, v["annual_rainfall_mm"])
    return {
        "village": v["village"],
        "total_acres": v["total_acres"],
        "zones": v["zones"],
        "land_split": {
            "agriculture_acres": v["agriculture_acres"],
            "non_agriculture_acres": v["non_agriculture_acres"],
            "agriculture_pct": agri_pct,
            "non_agriculture_pct": non_agri_pct,
        },
        "water_flow": {
            "flowing_acres": v["water_flowing_acres"],
            "not_flowing_acres": v["water_not_flowing_acres"],
            "excess_flow_acres": v["excess_water_acres"],
        },
        "classification": {
            "level": level,
            "annual_rainfall_mm": v["annual_rainfall_mm"],
            "reason": (
                f"Rainfall {v['annual_rainfall_mm']}mm/yr, "
                f"agriculture share {agri_pct}% of total land."
            ),
        },
    }


# ---------------------------------------------------------------------
# 2. WATERSHED PAGE
# ---------------------------------------------------------------------

def rain_status(mm_today: float) -> str:
    if mm_today > 80:
        return "Flood risk"
    if mm_today < 30:
        return "Drought risk"
    return "Normal"


def _estimate_rain_series_from_flow(water_bodies: dict, days: int = 14):
    """Create a stable rainfall estimate from the displayed watershed flow data.

    This is a visual planning estimate only, not a weather observation or forecast.
    Higher channel flow and a larger connected water-body network raise the baseline.
    """
    today = datetime.utcnow().date()
    connected_channels = water_bodies["rivers_count"] + water_bodies["streams_count"]
    flow_baseline = water_bodies["total_waterflow_lps"] / 55
    storage_adjustment = water_bodies["ponds_count"] * 1.8
    base_mm = max(5, min(75, flow_baseline + storage_adjustment + connected_channels * 1.5))
    recent_flow_variation = (-0.40, -0.24, -0.10, 0.08, 0.22, 0.36, 0.16, -0.05, -0.18, 0.04, 0.28, 0.12, -0.14, 0.20)
    series = []
    for i in range(days, 0, -1):
        d = today - timedelta(days=i)
        variation = recent_flow_variation[(days - i) % len(recent_flow_variation)]
        mm = round(max(0, base_mm * (1 + variation)), 1)
        series.append({"date": d.isoformat(), "rainfall_mm": mm})
    return series


WATER_BODIES = {
    "water_bodies": [
        {"id": "w1", "type": "river", "name": "Kaveri Feeder Channel",
         "path": "5,70 25,60 45,62 60,50 88,48"},
        {"id": "w2", "type": "pond", "name": "Doddakere Pond",
         "cx": 30, "cy": 30, "r": 6},
        {"id": "w3", "type": "pond", "name": "Chikkakere Pond",
         "cx": 70, "cy": 75, "r": 4.5},
        {"id": "w4", "type": "stream", "name": "Seasonal Stream",
         "path": "15,20 22,35 30,45 38,55"},
    ],
    "ponds_count": 2,
    "rivers_count": 1,
    "streams_count": 1,
    "main_water_body": "Kaveri Feeder Channel",
    "total_waterflow_lps": 1840,  # litres/sec, dummy
}


def location_water_bodies(location: Optional[str], profile: dict):
    water = deepcopy(WATER_BODIES)
    location_key = (location or "").strip().lower()
    city_stats = {
        "bengaluru": (3, 1, 2, 2120), "mysuru": (3, 1, 2, 1980),
        "pune": (2, 2, 2, 1760), "nashik": (3, 1, 1, 1640),
    }
    if location_key in city_stats:
        ponds, rivers, streams, flow = city_stats[location_key]
        water.update({"ponds_count": ponds, "rivers_count": rivers, "streams_count": streams, "total_waterflow_lps": flow})
    water["main_water_body"] = profile.get("main_water_body", water["main_water_body"])
    return water


@app.get("/api/watershed")
def watershed(location: Optional[str] = None):
    profile = location_profile(location)
    water = location_water_bodies(location, profile)
    series = _estimate_rain_series_from_flow(water, 14)
    today_mm = series[-1]["rainfall_mm"]
    total_mm_month = round(sum(s["rainfall_mm"] for s in series), 1)
    return {
        "village": profile["village"],
        "water_bodies": water["water_bodies"],
        "rain_series": series,
        "rain_series_note": "Approximate rainfall estimated from displayed flow-channel conditions.",
        "today_rainfall_mm": today_mm,
        "status": rain_status(today_mm),
        "water_body_stats": {
            "ponds_count": water["ponds_count"],
            "rivers_count": water["rivers_count"],
            "streams_count": water["streams_count"],
            "main_water_body": water["main_water_body"],
            "total_waterflow_lps": water["total_waterflow_lps"],
        },
        "rainfall_cm_today": round(today_mm / 10, 2),
        "rainfall_cm_month_total": round(total_mm_month / 10, 2),
    }


# ---------------------------------------------------------------------
# 3. GEO-TAGGED IMAGES PAGE
# ---------------------------------------------------------------------

GEO_IMAGES = [
    {
        "id": "img1",
        "officer": "Revenue Inspector - K. Suresh",
        "title": "Field boundary erosion near North Fields",
        "lat": 12.9721, "lng": 77.5946,
        "location_label": "North Fields, Hosahalli",
        "timestamp": "2026-09-18T09:32:00",
        "image_name": "pune-field.jpeg",
        "status": "Under review",
    },
    {
        "id": "img2",
        "officer": "Village Accountant - M. Latha",
        "title": "Illegal borewell reported",
        "lat": 12.9701, "lng": 77.6002,
        "location_label": "Rocky Belt, Hosahalli",
        "timestamp": "2026-09-20T14:05:00",
        "image_name": "nashik-park.jpeg",
        "status": "Escalated",
    },
    {
        "id": "img3",
        "officer": "Revenue Inspector - K. Suresh",
        "title": "Pond siltation - Doddakere",
        "lat": 12.9755, "lng": 77.5910,
        "location_label": "Doddakere Pond",
        "timestamp": "2026-09-22T11:15:00",
        "image_name": "water-garden.jpeg",
        "status": "Resolved",
    },
]


@app.get("/api/geo-images")
def geo_images(location: Optional[str] = None):
    selected_name = location_profile(location)["village"]
    images = deepcopy(GEO_IMAGES)
    for image in images:
        image["location_label"] = f"{selected_name} service area"
    return {"images": images}


# ---------------------------------------------------------------------
# 4. REPORT PAGE
# ---------------------------------------------------------------------

@app.post("/api/reports")
async def create_report(
    title: str = Form(...),
    description: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    image: UploadFile = File(...),
):
    if not image:
        raise HTTPException(400, "Image is mandatory")

    ext = Path(image.filename or "upload.jpg").suffix or ".jpg"
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / fname
    with dest.open("wb") as f:
        f.write(await image.read())

    report = {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "description": description,
        "lat": lat,
        "lng": lng,
        "image_url": f"/uploads/{fname}",
        "created_at": datetime.utcnow().isoformat(),
        "status": "Submitted",
    }
    with db_connection() as connection:
        connection.execute("""
            INSERT INTO reports (id, title, description, lat, lng, image_url, created_at, status)
            VALUES (:id, :title, :description, :lat, :lng, :image_url, :created_at, :status)
        """, report)
    return report


VALID_REPORT_STATUSES = {"Submitted", "Pending", "Approved", "Rejected"}


@app.get("/api/reports")
def list_reports():
    with db_connection() as connection:
        reports = connection.execute("SELECT * FROM reports ORDER BY created_at DESC").fetchall()
    return {"reports": [dict(report) for report in reports]}


@app.patch("/api/reports/{report_id}/status")
def update_report_status(report_id: str, payload: dict):
    status = (payload or {}).get("status")
    if status not in VALID_REPORT_STATUSES:
        raise HTTPException(400, "Invalid status value")

    with db_connection() as connection:
        updated = connection.execute(
            "UPDATE reports SET status = ? WHERE id = ?",
            (status, report_id),
        )
        if updated.rowcount == 0:
            raise HTTPException(404, "Report not found")
        report = connection.execute(
            "SELECT * FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()

    if report is None:
        raise HTTPException(404, "Report not found")
    return dict(report)


@app.get("/api/health")
def health():
    return {"ok": True}
