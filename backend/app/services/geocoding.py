import json

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Cell, District, GeocodeCache, Province, Sector


def _first(address: dict, *keys: str) -> str | None:
    return next((address[key] for key in keys if address.get(key)), None)


def reverse_geocode(db: Session, latitude: float, longitude: float) -> dict:
    key = f"reverse:{latitude:.5f}:{longitude:.5f}"
    cached = db.scalar(select(GeocodeCache).where(GeocodeCache.cache_key == key))
    if cached:
        return json.loads(cached.payload_json)
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": latitude, "lon": longitude, "format": "jsonv2", "addressdetails": 1, "accept-language": "en"},
            headers={"User-Agent": settings.nominatim_user_agent},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Map location service is temporarily unavailable") from exc
    raw = response.json()
    address = raw.get("address", {})
    country_code = address.get("country_code")
    if country_code and country_code.lower() != "rw":
        raise HTTPException(status_code=422, detail="Selected point is outside Rwanda")
    normalized = {
        "display_name": raw.get("display_name"),
        "province": _first(address, "state", "region"),
        "district": _first(address, "county", "state_district", "city"),
        "sector": _first(address, "municipality", "town", "suburb"),
        "cell": _first(address, "quarter", "neighbourhood"),
        "village": _first(address, "village", "hamlet", "residential"),
        "latitude": latitude,
        "longitude": longitude,
        "provider": "OpenStreetMap Nominatim",
        "needs_review": True,
    }
    db.add(GeocodeCache(cache_key=key, provider="nominatim", payload_json=json.dumps(normalized)))
    db.commit()
    return normalized


def search_locations(db: Session, query: str) -> list[dict]:
    normalized_query = " ".join(query.strip().split())
    key = f"search:{normalized_query.casefold()}"
    cached = db.scalar(select(GeocodeCache).where(GeocodeCache.cache_key == key))
    if cached:
        return json.loads(cached.payload_json)
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": normalized_query, "countrycodes": "rw", "format": "jsonv2", "addressdetails": 1, "accept-language": "en", "limit": 6},
            headers={"User-Agent": settings.nominatim_user_agent},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Map search service is temporarily unavailable") from exc
    results = []
    for item in response.json():
        address = item.get("address", {})
        if address.get("country_code", "rw").lower() != "rw":
            continue
        results.append({
            "display_name": item.get("display_name"), "latitude": float(item["lat"]), "longitude": float(item["lon"]),
            "province": _first(address, "state", "region"), "district": _first(address, "county", "state_district", "city"),
            "sector": _first(address, "municipality", "town", "suburb"), "cell": _first(address, "quarter", "neighbourhood"),
            "village": _first(address, "village", "hamlet", "residential"), "provider": "OpenStreetMap Nominatim", "needs_review": True,
        })
    db.add(GeocodeCache(cache_key=key, provider="nominatim", payload_json=json.dumps(results)))
    db.commit()
    return results


def cell_map_focus(db: Session, cell_code: int) -> dict:
    key = f"cell-focus:{cell_code}"
    cached = db.scalar(select(GeocodeCache).where(GeocodeCache.cache_key == key))
    if cached:
        return json.loads(cached.payload_json)

    cell = db.get(Cell, cell_code)
    sector = db.get(Sector, cell.sector_code) if cell else None
    district = db.get(District, sector.district_code) if sector else None
    province = db.get(Province, district.province_code) if district else None
    if not all((cell, sector, district, province)):
        raise HTTPException(status_code=404, detail="Cell hierarchy not found")

    queries = [
        (f"{cell.name}, {sector.name}, {district.name}, Rwanda", "cell"),
        (f"{sector.name}, {district.name}, Rwanda", "sector"),
        (f"{district.name}, Rwanda", "district"),
    ]
    try:
        match = None
        focus_level = "cell"
        for query, level in queries:
            response = httpx.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "countrycodes": "rw", "format": "jsonv2", "polygon_geojson": 1, "addressdetails": 1, "limit": 3},
                headers={"User-Agent": settings.nominatim_user_agent},
                timeout=12,
            )
            response.raise_for_status()
            matches = response.json()
            if matches:
                match = matches[0]
                focus_level = level
                break
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Cell map lookup is temporarily unavailable") from exc
    if not match:
        raise HTTPException(status_code=404, detail="This area could not be located on OpenStreetMap")
    bounds = match.get("boundingbox")
    result = {
        "cell_code": cell.code,
        "label": f"{cell.name} Cell, {sector.name} Sector",
        "latitude": float(match["lat"]),
        "longitude": float(match["lon"]),
        "bounds": [float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])] if bounds else None,
        "geometry": match.get("geojson"),
        "provider": "OpenStreetMap Nominatim",
        "focus_level": focus_level,
        "exact_cell_match": focus_level == "cell",
        "navigation_only": True,
    }
    db.add(GeocodeCache(cache_key=key, provider="nominatim", payload_json=json.dumps(result)))
    db.commit()
    return result

