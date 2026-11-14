"""
Earth Trend Explorer — NASA GISTEMP v4 FastAPI bridge.

Downloads the official NASA GISS Surface Temperature Analysis (GISTEMP v4)
land-ocean global means CSV, extracts the annual (J-D) anomalies, and exposes
them as JSON for the dashboard's Global Temperature card and trend chart.

Run from the backend directory:
    python -m uvicorn main:app --reload --port 8001

Endpoint:
    GET http://127.0.0.1:8001/api/temperature
    GET http://127.0.0.1:8001/api/health

No API keys are required. The upstream CSV is cached in memory to avoid
unnecessary requests to NASA.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# =============================================================================
# CONFIGURATION
# =============================================================================
GISTEMP_CSV_URL = os.getenv(
    "GISTEMP_CSV_URL",
    "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv",
)
GISTEMP_CACHE_TTL_SECONDS = max(
    0, int(os.getenv("GISTEMP_CACHE_TTL_SECONDS", "3600"))
)
GISTEMP_REQUEST_TIMEOUT_SECONDS = max(
    1.0, float(os.getenv("GISTEMP_REQUEST_TIMEOUT_SECONDS", "25"))
)

# Comma-separated list so the frontend can be served from any local port.
_default_origins = (
    "https://earthtrendexplorer-web.onrender.com,"
    "http://localhost:5500,http://127.0.0.1:5500"
)
_local_network_origin_regex = (
    r"^https?://(?:localhost|127(?:\.\d{1,3}){3}|"
    r"10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?::\d+)?$"
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

BASELINE = "1951–1980"
UNIT = "°C"

logger = logging.getLogger("earth-trend-explorer")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Earth Trend Explorer — NASA Telemetry API",
    description=(
        "Read-only FastAPI bridge exposing real NASA GISTEMP v4 annual "
        "global temperature anomalies to the Earth Trend Explorer dashboard."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=_local_network_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


# =============================================================================
# NASA GISTEMP INGESTION
# =============================================================================
def download_gistemp_csv() -> str:
    """Download the GISTEMP v4 global-means CSV using the standard library."""
    request = Request(
        GISTEMP_CSV_URL,
        headers={
            "User-Agent": "EarthTrendExplorer/1.0 (local NASA dashboard)",
            "Accept": "text/csv,text/plain,*/*",
        },
    )
    with urlopen(request, timeout=GISTEMP_REQUEST_TIMEOUT_SECONDS) as response:
        body = response.read()

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("NASA GISTEMP CSV could not be decoded as text.")


def parse_gistemp_csv(csv_text: str) -> list[dict[str, Any]]:
    """
    Extract annual (J-D) global temperature anomalies from the GISTEMP CSV.

    The CSV starts with a title line, then a normal header row. The `J-D`
    column is the annual mean anomaly; `***` indicates an incomplete year
    (for example the current year before December data is available) and is
    skipped so only complete annual observations are exposed.
    """
    lines = csv_text.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if line.lstrip().startswith("Year")),
        None,
    )
    if header_index is None:
        raise ValueError("Unexpected NASA GISTEMP CSV format: missing header row.")

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
    if not reader.fieldnames or "Year" not in reader.fieldnames:
        raise ValueError("Unexpected NASA GISTEMP CSV format: missing Year column.")

    annual_by_year: dict[int, float] = {}

    for row in reader:
        year_raw = (row.get("Year") or "").strip()
        annual_raw = (row.get("J-D") or "").strip()

        if not year_raw.isdigit():
            continue
        if annual_raw in {"", "***", "NaN", "nan", "N/A"}:
            continue

        try:
            year = int(year_raw)
            anomaly = float(annual_raw)
        except ValueError:
            continue

        # Basic scientific sanity checks to reject malformed rows.
        if not 1800 <= year <= 2200:
            continue
        if not -20.0 <= anomaly <= 20.0:
            continue

        annual_by_year[year] = round(anomaly, 2)

    if not annual_by_year:
        raise ValueError("NASA GISTEMP CSV contained no complete annual values.")

    return [
        {"year": year, "temperature_anomaly": annual_by_year[year]}
        for year in sorted(annual_by_year)
    ]


def build_temperature_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Create the JSON contract consumed by index.html."""
    latest = records[-1]
    return {
        "source": "NASA GISTEMP v4",
        "dataset": (
            "GISS Surface Temperature Analysis (GISTEMP v4) — "
            "Land-Ocean Global Means"
        ),
        "unit": UNIT,
        "baseline": BASELINE,
        "data_type": "Annual Global Temperature Anomaly",
        "year": latest["year"],
        "temperature_anomaly": latest["temperature_anomaly"],
        "data": records,
        "record_count": len(records),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_url": GISTEMP_CSV_URL,
    }


# =============================================================================
# IN-MEMORY CACHE (avoids repeated NASA requests)
# =============================================================================
_cache_payload: dict[str, Any] | None = None
_cache_expires_at = 0.0
_cache_lock = asyncio.Lock()


async def get_temperature_payload() -> dict[str, Any]:
    global _cache_payload, _cache_expires_at

    now = time.monotonic()
    if _cache_payload is not None and now < _cache_expires_at:
        return _cache_payload

    async with _cache_lock:
        now = time.monotonic()
        if _cache_payload is not None and now < _cache_expires_at:
            return _cache_payload

        # Network I/O is blocking; keep the event loop responsive.
        csv_text = await asyncio.to_thread(download_gistemp_csv)
        records = parse_gistemp_csv(csv_text)
        payload = build_temperature_payload(records)

        _cache_payload = payload
        _cache_expires_at = time.monotonic() + GISTEMP_CACHE_TTL_SECONDS
        return payload


# =============================================================================
# API ROUTES
# =============================================================================
@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "Earth Trend Explorer NASA Telemetry API",
        "status": "online",
        "temperature_endpoint": "/api/temperature",
        "health_endpoint": "/api/health",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "Earth Trend Explorer NASA Telemetry API",
        "source": "NASA GISTEMP v4",
        "cached": _cache_payload is not None and time.monotonic() < _cache_expires_at,
        "cache_ttl_seconds": GISTEMP_CACHE_TTL_SECONDS,
    }


@app.get("/api/temperature")
async def temperature() -> dict[str, Any]:
    try:
        return await get_temperature_payload()
    except Exception as exc:  # noqa: BLE001 - return a clean API error to the UI
        logger.exception("Failed to retrieve or parse NASA GISTEMP v4 data")
        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to retrieve NASA GISTEMP v4 data right now. "
                "Check the backend internet connection and try again."
            ),
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
