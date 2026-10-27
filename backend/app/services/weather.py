import json
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import WeatherCache


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CACHE_MINUTES = 30


def _previous_months(count: int = 12) -> tuple[date, date]:
    end = date.today().replace(day=1) - timedelta(days=1)
    month_index = end.year * 12 + end.month - count
    start = date(month_index // 12, month_index % 12 + 1, 1)
    return start, end


def _monthly_summaries(raw: dict) -> list[dict]:
    daily = raw.get("daily", {})
    buckets: dict[str, dict] = {}
    for index, day in enumerate(daily.get("time", [])):
        month = day[:7]
        bucket = buckets.setdefault(month, {"month": month, "rainfall_mm": 0.0, "highs": [], "lows": [], "days": 0})
        bucket["rainfall_mm"] += float((daily.get("precipitation_sum") or [0])[index] or 0)
        high = (daily.get("temperature_2m_max") or [None])[index]
        low = (daily.get("temperature_2m_min") or [None])[index]
        if high is not None:
            bucket["highs"].append(float(high))
        if low is not None:
            bucket["lows"].append(float(low))
        bucket["days"] += 1
    return [
        {
            "month": item["month"],
            "rainfall_mm": round(item["rainfall_mm"], 1),
            "mean_high_c": round(sum(item["highs"]) / len(item["highs"]), 1) if item["highs"] else None,
            "mean_low_c": round(sum(item["lows"]) / len(item["lows"]), 1) if item["lows"] else None,
            "days": item["days"],
        }
        for item in buckets.values()
    ]


def _recommendations(forecast: dict) -> list[dict]:
    hourly = forecast.get("hourly", {})
    rain = [float(value or 0) for value in (hourly.get("precipitation") or [])[:24]]
    probability = [float(value or 0) for value in (hourly.get("precipitation_probability") or [])[:24]]
    wind = [float(value or 0) for value in (hourly.get("wind_speed_10m") or [])[:24]]
    humidity = [float(value or 0) for value in (hourly.get("relative_humidity_2m") or [])[:24]]
    rain_total = round(sum(rain), 1)
    rain_chance = round(max(probability, default=0))
    wind_max = round(max(wind, default=0), 1)
    humidity_mean = round(sum(humidity) / len(humidity)) if humidity else None
    evidence = f"Next 24 hours: {rain_total} mm modelled rain, up to {rain_chance}% rain probability"
    if humidity_mean is not None:
        evidence += f", and {humidity_mean}% mean humidity"
    if rain_total >= 3 or rain_chance >= 60:
        guidance = "Rain is likely within the next 24 hours. Consider postponing irrigation if a field check confirms the soil is already moist."
        title = "Review irrigation timing"
    else:
        guidance = "Little rain is currently indicated. Inspect soil moisture and crop stress before deciding whether to irrigate."
        title = "Check soil moisture"
    items = [{
        "title": title,
        "guidance": guidance,
        "evidence": evidence,
        "uncertainty": "Forecasts can shift and no farm soil-moisture sensor or crop growth-stage record is connected, so this is decision support—not an automatic instruction.",
        "severity": "attention" if rain_total >= 3 or rain_chance >= 60 else "normal",
    }]
    if wind_max >= 30:
        items.append({
            "title": "Delay spraying in strong wind",
            "guidance": "Avoid spraying during the windiest hours to reduce chemical drift.",
            "evidence": f"The highest modelled wind speed in the next 24 hours is {wind_max} km/h.",
            "uncertainty": "Local gusts can be stronger or weaker than the modelled grid-cell value.",
            "severity": "warning",
        })
    return items


def weather_dashboard(db: Session, latitude: float, longitude: float, label: str, source: str) -> dict:
    if not (-2.95 <= latitude <= -0.95 and 28.8 <= longitude <= 30.95):
        raise HTTPException(status_code=422, detail="Weather coordinates must be inside Rwanda")
    key = f"weather:{latitude:.3f}:{longitude:.3f}"
    fresh_after = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=CACHE_MINUTES)
    cached = db.scalar(select(WeatherCache).where(WeatherCache.cache_key == key, WeatherCache.created_at >= fresh_after))
    if cached:
        result = json.loads(cached.payload_json)
        result["cache"] = {"hit": True, "stored_at": cached.created_at.isoformat()}
        result["location"].update({"label": label, "source": source})
        return result

    forecast_params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,rain,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,precipitation_probability_max,wind_speed_10m_max",
        "timezone": "Africa/Kigali",
        "forecast_days": 7,
    }
    history_start, history_end = _previous_months()
    history_params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": history_start.isoformat(),
        "end_date": history_end.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Africa/Kigali",
    }
    try:
        forecast_response = httpx.get(FORECAST_URL, params=forecast_params, timeout=15)
        forecast_response.raise_for_status()
        history_response = httpx.get(ARCHIVE_URL, params=history_params, timeout=20)
        history_response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Weather service is temporarily unavailable") from exc

    forecast = forecast_response.json()
    result = {
        "location": {"label": label, "source": source, "latitude": latitude, "longitude": longitude, "timezone": forecast.get("timezone", "Africa/Kigali")},
        "current": forecast.get("current", {}),
        "current_units": forecast.get("current_units", {}),
        "hourly": forecast.get("hourly", {}),
        "hourly_units": forecast.get("hourly_units", {}),
        "daily": forecast.get("daily", {}),
        "daily_units": forecast.get("daily_units", {}),
        "historical_months": _monthly_summaries(history_response.json()),
        "historical_note": "Monthly historical summary from model-assisted reanalysis. These are past estimates, not forecasts or exact weather-station observations.",
        "recommendations": _recommendations(forecast),
        "warnings": [],
        "warnings_supported": False,
        "warnings_note": "Open-Meteo does not provide an official Rwanda weather-warning feed. Model-based agricultural advisories are shown separately.",
        "provider": "Open-Meteo",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cache": {"hit": False, "ttl_minutes": CACHE_MINUTES},
    }
    db.query(WeatherCache).filter(WeatherCache.cache_key == key).delete()
    db.add(WeatherCache(cache_key=key, provider="open-meteo", payload_json=json.dumps(result)))
    db.commit()
    return result
