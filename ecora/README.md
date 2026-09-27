# Ecora — Land & Watershed Monitoring Dashboard (Prototype)

Dark, glass-panel theme matching the reference branding ("ECORA — Track. Analyze. Grow").
All data is **dummy data** for now, served from the FastAPI backend — swap in real
GIS / rainfall / survey data later without touching the frontend markup (just change
what `main.py` returns).

## Structure
```
ecora/
├── backend/
│   ├── main.py            FastAPI app — all endpoints + dummy data + rule logic
│   ├── requirements.txt
│   └── uploads/            (created automatically — stores report photos)
└── frontend/
    ├── index.html          Page 1: Land map, agri vs non-agri bar chart,
    │                       water-flow stats, high/moderate/low classification
    ├── watershed.html      Page 2: water-body map, rainfall graph, water-body
    │                       stats, flood/drought/normal status, rainfall in cm
    ├── geo-images.html     Page 3: gallery of officials' geo-tagged report photos
    ├── report.html         Page 4: new report form — title, description,
    │                       mandatory photo, geolocation
    ├── settings.html       Page 5: app preference toggles
    └── assets/
        ├── style.css       shared dark-forest / glass theme
        └── app.js           shared sidebar nav + API helper
```

## Run the backend
```bash
cd backend
python -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Backend will be live at `http://127.0.0.1:8000`. Interactive API docs at
`http://127.0.0.1:8000/docs`.

## Run the frontend
No build step — plain HTML/CSS/JS + Chart.js (loaded from CDN). Just open
`frontend/index.html` in a browser, **or** serve the folder so `fetch()` isn't
blocked by `file://` restrictions in some browsers:
```bash
cd frontend
python -m http.server 5500
```
Then visit `http://127.0.0.1:5500`.

If your backend runs on a different host/port, update `API_BASE` at the top of
`frontend/assets/app.js`.

## Where the "rules" you described live
All in `backend/main.py`, easy to find and tune:
- `classify_village_level()` — High / Moderate / Low land classification from
  agriculture share + annual rainfall.
- `rain_status()` — Flood (>80mm) / Drought (<30mm) / Normal, used on the
  Watershed page.

## Notes / next steps
- The land map and watershed map are stylised SVGs built from simple polygon /
  point data in `main.py` (`VILLAGE_LAND["zones"]`, `WATER_BODIES`) — replace
  those coordinates with real surveyed GeoJSON when you have it, or swap the
  SVG for a Leaflet/Mapbox map if you want real satellite tiles.
- Report photos are saved to `backend/uploads/` and served at `/uploads/...`;
  swap for S3/cloud storage later.
- I couldn't open the Figma link directly (no browser access on my end), so
  the layout follows your written spec and the reference screenshot's theme —
  send exported PNGs of specific Figma frames if you want pixel-level matching.
- Matches the React+Vite+Tailwind / Python backend pattern from your resume
  analyzer project in spirit, but I kept this frontend framework-free (no
  build step) since you said dummy data is just for now — happy to port it to
  React+Vite+Tailwind if that's what you want to keep long-term.
