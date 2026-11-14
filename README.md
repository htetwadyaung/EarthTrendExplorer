# Earth Trend Explorer

Earth Trend Explorer is a prototype for exploring NASA's annual global temperature record on an interactive Earth. The main path is simple: view the globe, open the NASA temperature trend, and check each data source and status.

## What the prototype shows

- **Global temperature:** annual global temperature anomalies from NASA GISTEMP v4, retrieved through the local FastAPI bridge when available.
- **Other indicators:** atmospheric CO₂, sea level, Arctic sea ice, and active fire hotspot examples are **SIMULATED / DEMO DATA**. They are not connected to live feeds.
- **Earth interaction:** rotate and zoom the Three.js sphere using NASA/JPL's *Earth* Blue Marble mosaic (PIA18033), made from Suomi NPP VIIRS imagery. Select a marker or surface coordinate to see its location and regional data availability; the prototype does not invent local measurements.
- **Maps and analysis:** explore the existing map, regional comparisons, charts, and satellite mission views. Demo map markers and regional values are not live observations.

> **Data integrity:** only a valid response from the FastAPI bridge is labelled LIVE NASA GISTEMP data. If the bridge is unavailable, the temperature display falls back to simulated values. The remaining four indicators stay simulated in either case.

## Competition project summary

The prototype centers on NASA GISTEMP v4 annual global temperature anomalies. For a NASA Space Apps Challenge submission, connect this summary to the exact challenge selected by your team and explain the specific user problem, the NASA data used, and the intended impact. Secondary indicator and map modules remain demonstrations; do not describe their simulated values as NASA observations.

## Credits and references

- **NASA GISTEMP v4 annual global land-ocean means:** [NASA GISS dataset and downloads](https://data.giss.nasa.gov/gistemp/data_v4.html); the API reads the annual `J-D` column from the [CSV](https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv). Values are anomalies relative to 1951–1980.
- **Earth texture:** NASA/JPL, [Earth (PIA18033)](https://www.jpl.nasa.gov/images/pia18033-earth/), a Blue Marble mosaic based on imagery from the VIIRS instrument aboard Suomi NPP. Credit: NASA.
- **Interactive 3D:** [Three.js](https://threejs.org/) (r128).
- **2D map:** [Leaflet](https://leafletjs.com/) (1.9.4), [TopoJSON Client](https://github.com/topojson/topojson-client) (3.1.0), and [World Atlas](https://github.com/topojson/world-atlas) (2, Natural Earth country boundaries).
- **Interface resources:** [Tailwind CSS](https://tailwindcss.com/), [Lucide](https://lucide.dev/), and Google Fonts (Inter, Space Grotesk, JetBrains Mono).

The NASA data and image are credited to their source. For the competition submission, cite every project resource in the official References field and select an appropriate open-source license for the original project materials.

## Run locally

Requirements: Python 3.10+ and internet access for retrieving the NASA GISTEMP CSV.

Install backend dependencies:

```powershell
cd D:\EarthTrendExplorer
python -m pip install -r backend\requirements.txt
```

Start the API in one terminal:

```powershell
cd D:\EarthTrendExplorer\backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

Start the frontend in a second terminal:

```powershell
cd D:\EarthTrendExplorer
python -m http.server 8000 --bind 0.0.0.0
```

On the computer, open <http://localhost:8000>. To open the dashboard on a phone connected to the same Wi-Fi, use the computer's LAN address, for example <http://192.168.100.35:8000>. Keep both servers running. The page automatically points its API request to the same LAN address on port 8001.

Make sure the phone and computer are on the same Wi-Fi and that the computer's current LAN address still matches the URL. If Windows Firewall blocks the connection, run this once in **PowerShell as Administrator** to allow only these ports from the local subnet on the Private profile:

```powershell
New-NetFirewallRule -DisplayName "EarthTrendExplorer LAN dashboard and API" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000,8001 -Profile Private -RemoteAddress LocalSubnet
```

Serve the page over HTTP rather than opening `index.html` directly; a `file://` page cannot use the configured FastAPI CORS connection.

## NASA GISTEMP API

- `GET http://127.0.0.1:8001/api/temperature` returns the complete annual series and latest complete annual anomaly.
- `GET http://127.0.0.1:8001/api/health` reports bridge status.
- `GET http://127.0.0.1:8001/docs` opens the interactive API documentation.

The bridge reads the annual `J-D` column from the official [NASA GISTEMP v4 global means CSV](https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv), skips incomplete values, and caches the upstream response in memory for one hour by default. A temperature anomaly is measured against the GISTEMP **1951–1980** baseline; it is not an absolute temperature.

### Configuration

- Frontend API base URL: `API_CONFIG.baseUrl` in `index.html` (defaults to the page's hostname on port `8001`; use `127.0.0.1` when opened on the same computer). It can be overridden before the main script runs with `window.EARTH_TREND_API_BASE`.
- Backend environment variables: `GISTEMP_CSV_URL`, `GISTEMP_CACHE_TTL_SECONDS` (default `3600`), `GISTEMP_REQUEST_TIMEOUT_SECONDS` (default `25`), and `CORS_ORIGINS` (comma-separated allowed frontend origins).
- No API keys or secrets are required.

## Project files

```text
EarthTrendExplorer/
├── index.html                    # Dashboard, charts, maps, and Three.js globe
├── assets/
│   └── earth-blue-marble-daytime.jpg  # NASA Blue Marble daytime Earth texture
├── backend/
│   ├── main.py                   # NASA GISTEMP FastAPI bridge
│   └── requirements.txt          # Backend dependencies
└── README.md
```

## Demo and review checklist

1. Open the dashboard and confirm the temperature indicator reports LIVE only after a valid API response.
2. Inspect Temperature Trends and its NASA source, baseline, unit, and annual series.
3. Confirm CO₂, sea level, Arctic sea ice, and fire indicators remain labelled SIMULATED.
4. Rotate and zoom the globe; select a hotspot marker and inspect the regional profile.
5. Switch dashboard views and confirm the map and charts remain interactive.
6. Stop the API and reload to confirm the dashboard identifies its fallback as simulated; restart it and retry the connection.

## Limitations

This is a prototype, not a comprehensive operational climate-monitoring service. Four indicator series and regional hotspot profiles are illustrative simulated data. The NASA GISTEMP bridge supplies global annual temperature anomalies only; it does not supply the regional marker measurements.
