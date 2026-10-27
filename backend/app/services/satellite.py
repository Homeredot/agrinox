import json
import math
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings


TOKEN_URL = f"{settings.planet_sentinel_base_url}/auth/realms/main/protocol/openid-connect/token"
CATALOG_URL = f"{settings.planet_sentinel_base_url}/api/v1/catalog/1.0.0/search"
STATS_URL = f"{settings.planet_sentinel_base_url}/api/v1/statistics"
PROCESS_URL = f"{settings.planet_sentinel_base_url}/api/v1/process"
COLLECTION = "sentinel-2-l2a"
_token: dict[str, Any] = {"value": None, "expires": 0.0}
_token_lock = threading.Lock()

NDVI_STATS_SCRIPT = """//VERSION=3
function setup() {
  return {input:["B04","B08","SCL","dataMask"], output:[
    {id:"ndvi", bands:1, sampleType:"FLOAT32"},
    {id:"dataMask", bands:1}
  ]};
}
function evaluatePixel(s) {
  const clear = s.dataMask === 1 && ![0,1,3,8,9,10,11].includes(s.SCL);
  const denominator = s.B08 + s.B04;
  return {ndvi:[denominator === 0 ? 0 : (s.B08-s.B04)/denominator], dataMask:[clear ? 1 : 0]};
}"""

NDVI_IMAGE_SCRIPT = """//VERSION=3
function setup(){return {input:["B04","B08","SCL","dataMask"],output:{bands:4}};}
function evaluatePixel(s){
  if(s.dataMask===0 || [0,1,3,8,9,10,11].includes(s.SCL)) return [0,0,0,0];
  const d=s.B08+s.B04; const n=d===0?0:(s.B08-s.B04)/d;
  if(n<0) return [0.32,0.44,0.72,1];
  if(n<0.2) return [0.73,0.52,0.27,1];
  if(n<0.4) return [0.84,0.76,0.31,1];
  if(n<0.6) return [0.49,0.69,0.25,1];
  return [0.10,0.45,0.18,1];
}"""


def integration_status() -> dict[str, Any]:
    configured = bool(settings.planet_client_id and settings.planet_client_secret)
    return {
        "provider": "Planet Insights Platform",
        "collection": COLLECTION,
        "configured": configured,
        "status": "ready" if configured else "credentials_required",
        "message": "Planet Sentinel-2 connection is ready." if configured else "Add Planet OAuth client credentials to enable real Sentinel-2 imagery and NDVI.",
        "simulated": False,
    }


def circle_geometry(latitude: float, longitude: float, radius_m: float, vertices: int = 48) -> dict[str, Any]:
    lat_scale = 111_320.0
    lon_scale = lat_scale * max(math.cos(math.radians(latitude)), 0.2)
    ring = []
    for index in range(vertices):
        angle = 2 * math.pi * index / vertices
        ring.append([longitude + math.cos(angle) * radius_m / lon_scale, latitude + math.sin(angle) * radius_m / lat_scale])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def bbox_for_geometry(geometry: dict[str, Any]) -> list[float]:
    if geometry.get("type") != "Polygon" or not geometry.get("coordinates"):
        raise ValueError("A Polygon field boundary is required for satellite monitoring")
    ring = geometry["coordinates"][0]
    if len(ring) < 4:
        raise ValueError("The field boundary needs at least three points")
    lngs = [float(point[0]) for point in ring]
    lats = [float(point[1]) for point in ring]
    return [min(lngs), min(lats), max(lngs), max(lats)]


def _access_token() -> str:
    if not settings.planet_client_id or not settings.planet_client_secret:
        raise RuntimeError("Planet OAuth credentials are not configured")
    with _token_lock:
        if _token["value"] and time.time() < float(_token["expires"]) - 60:
            return str(_token["value"])
        response = httpx.post(TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": settings.planet_client_id,
            "client_secret": settings.planet_client_secret,
        }, timeout=20)
        response.raise_for_status()
        payload = response.json()
        _token["value"] = payload["access_token"]
        _token["expires"] = time.time() + int(payload.get("expires_in", 600))
        return str(_token["value"])


def _headers(accept: str = "application/json") -> dict[str, str]:
    return {"Authorization": f"Bearer {_access_token()}", "Accept": accept}


def _iso(day: date, end: bool = False) -> str:
    value = datetime.combine(day + (timedelta(days=1) if end else timedelta()), datetime.min.time(), tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _catalog(geometry: dict[str, Any], start: date, end: date) -> list[dict[str, Any]]:
    response = httpx.post(CATALOG_URL, headers={**_headers("application/geo+json"), "Content-Type": "application/json"}, json={
        "collections": [COLLECTION], "bbox": bbox_for_geometry(geometry),
        "datetime": f"{_iso(start)}/{_iso(end, True)}", "limit": 30,
        "filter": "eo:cloud_cover <= 80", "filter-lang": "cql2-text",
    }, timeout=35)
    response.raise_for_status()
    return response.json().get("features", [])


def _statistics(geometry: dict[str, Any], start: date, end: date) -> dict[str, Any]:
    response = httpx.post(STATS_URL, headers={**_headers(), "Content-Type": "application/json"}, json={
        "input": {"bounds": {"geometry": geometry}, "data": [{"type": COLLECTION, "dataFilter": {"mosaickingOrder": "leastCC"}}]},
        "aggregation": {"timeRange": {"from": _iso(start), "to": _iso(end, True)}, "aggregationInterval": {"of": "P10D"}, "resx": 10, "resy": 10, "evalscript": NDVI_STATS_SCRIPT},
        "calculations": {"ndvi": {"statistics": {"default": {"percentiles": {"k": [25, 50, 75]}}}}},
    }, timeout=50)
    response.raise_for_status()
    return response.json()


def _trend(stats_payload: dict[str, Any]) -> list[dict[str, Any]]:
    geometry_pixels = int(stats_payload.get("geometryPixelCount") or 0)
    values: list[dict[str, Any]] = []
    for interval in stats_payload.get("data", []):
        band = (((interval.get("outputs") or {}).get("ndvi") or {}).get("bands") or {}).get("B0") or {}
        stats = band.get("stats") or {}
        sample_count, no_data = int(stats.get("sampleCount") or 0), int(stats.get("noDataCount") or 0)
        valid_pixels = max(0, sample_count - no_data)
        if stats.get("mean") is None or valid_pixels == 0:
            continue
        valid_percent = round(min(100.0, valid_pixels / geometry_pixels * 100), 1) if geometry_pixels else None
        values.append({
            "date": (interval.get("interval") or {}).get("from", "")[:10],
            "ndvi": round(float(stats["mean"]), 3),
            "ndvi_min": round(float(stats.get("min", stats["mean"])), 3),
            "ndvi_max": round(float(stats.get("max", stats["mean"])), 3),
            "valid_area_percent": valid_percent,
        })
    return values


def satellite_dashboard(geometry: dict[str, Any], label: str, source_mode: str, start: date, end: date) -> dict[str, Any]:
    base = {
        "integration": integration_status(), "area": {"label": label, "source_mode": source_mode, "geometry": geometry, "bbox": bbox_for_geometry(geometry)},
        "spatial_resolution_m": 10, "latest": None, "trend": [], "comparison": None, "unusual_changes": [], "imagery_available": False,
        "limitations": ["NDVI indicates vegetation greenness, not a disease diagnosis.", "Cloud, cloud shadow and no-data pixels are excluded; a low valid area weakens interpretation."],
        "simulated": False,
    }
    if not base["integration"]["configured"]:
        base["limitations"].insert(0, "Live Sentinel-2 access is not configured. No satellite values are shown.")
        return base
    try:
        features = _catalog(geometry, start, end)
        stats_payload = _statistics(geometry, start, end)
        trend = _trend(stats_payload)
        if not features or not trend:
            base["integration"] = {**base["integration"], "status": "no_valid_observation", "message": "No clear Sentinel-2 observation was available for this area and date range."}
            base["limitations"].insert(0, "No valid cloud-filtered observation is available in the selected period.")
            return base
        features.sort(key=lambda item: str((item.get("properties") or {}).get("datetime", "")))
        newest = features[-1]
        props = newest.get("properties") or {}
        base["trend"] = trend
        base["latest"] = {
            "acquisition_date": str(props.get("datetime", ""))[:10] or trend[-1]["date"],
            "cloud_coverage_percent": props.get("eo:cloud_cover"),
            "cloud_coverage_scope": "source scene",
            "ndvi": trend[-1]["ndvi"], "valid_area_percent": trend[-1]["valid_area_percent"],
        }
        if len(trend) >= 2:
            delta = round(trend[-1]["ndvi"] - trend[-2]["ndvi"], 3)
            base["comparison"] = {"previous_date": trend[-2]["date"], "previous_ndvi": trend[-2]["ndvi"], "change": delta}
        changes = []
        for previous, current in zip(trend, trend[1:]):
            delta = round(current["ndvi"] - previous["ndvi"], 3)
            if delta <= -0.15 and (current["valid_area_percent"] or 0) >= 50:
                changes.append({"date": current["date"], "change": delta, "severity": "review", "message": "NDVI fell by at least 0.15 between valid observations. Inspect the field; this is not a diagnosis."})
        base["unusual_changes"] = changes
        base["imagery_available"] = True
        return base
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        base["integration"] = {**base["integration"], "status": "unavailable", "message": "Sentinel-2 service could not be reached. No measurements were invented."}
        base["limitations"].insert(0, f"Live integration error: {type(exc).__name__}.")
        return base


def ndvi_image(geometry: dict[str, Any], start: date, end: date) -> bytes:
    response = httpx.post(PROCESS_URL, headers={**_headers("image/png"), "Content-Type": "application/json"}, json={
        "input": {"bounds": {"geometry": geometry}, "data": [{"type": COLLECTION, "dataFilter": {"timeRange": {"from": _iso(start), "to": _iso(end, True)}, "mosaickingOrder": "leastCC"}}]},
        "output": {"width": 768, "height": 768, "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
        "evalscript": NDVI_IMAGE_SCRIPT,
    }, timeout=60)
    response.raise_for_status()
    return response.content
