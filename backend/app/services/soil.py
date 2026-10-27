import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Device, FarmField, Sensor, SensorReading, SoilReading, WeatherCache

MEASUREMENTS = ("nitrogen", "phosphorus", "potassium", "moisture", "temperature", "ph")
LABELS = {
    "nitrogen": "Nitrogen (N)",
    "phosphorus": "Phosphorus (P)",
    "potassium": "Potassium (K)",
    "moisture": "Soil moisture",
    "temperature": "Soil temperature",
    "ph": "Soil pH",
}
DEFAULT_UNITS = {
    "nitrogen": "mg/kg", "phosphorus": "mg/kg", "potassium": "mg/kg",
    "moisture": "%", "temperature": "°C", "ph": "pH",
}
VALID_UNITS = {
    "nitrogen": {"mg/kg", "ppm"},
    "phosphorus": {"mg/kg", "ppm"},
    "potassium": {"mg/kg", "ppm"},
    "moisture": {"%"},
    "temperature": {"°c", "c", "celsius"},
    "ph": {"ph"},
}
CROP_PH_RANGES = {
    "rice": (5.5, 7.5),
    "potato": (5.0, 5.4),
    "maize": (5.5, 7.0),
    "beans": (5.5, 6.8),
}
REALTIME_TYPES = {"moisture", "temperature"}
KIGALI_TZ = timezone(timedelta(hours=2))


def crop_group(crop_type: str | None) -> str:
    crop = (crop_type or "").strip().lower()
    if any(name in crop for name in ("rice", "paddy", "umuceri")):
        return "rice"
    if any(name in crop for name in ("potato", "ibirayi")):
        return "potato"
    if any(name in crop for name in ("maize", "corn", "ibigori")):
        return "maize"
    if any(name in crop for name in ("bean", "ibishyimbo")):
        return "beans"
    return "other"


def utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def normalized_unit(unit: str | None) -> str:
    return (unit or "").strip().lower().replace("℃", "°c")


def is_compatible_unit(kind: str, unit: str | None) -> bool:
    return normalized_unit(unit) in VALID_UNITS[kind]


def freshness_limit(kind: str) -> timedelta:
    return timedelta(hours=24) if kind in REALTIME_TYPES else timedelta(days=180)


def decorate_reading(kind: str, reading: dict, now: datetime) -> dict:
    measured_at = utc_datetime(datetime.fromisoformat(reading["timestamp"]))
    age_hours = max(0.0, (now - measured_at).total_seconds() / 3600)
    compatible = is_compatible_unit(kind, reading.get("unit"))
    stale = now - measured_at > freshness_limit(kind)
    if not compatible or reading.get("reliability") == "unreliable":
        quality = "unusable"
    elif stale:
        quality = "stale"
    elif reading.get("source") == "laboratory" and reading.get("reliability") == "reliable":
        quality = "verified"
    elif reading.get("calibration_status") == "calibrated" and reading.get("reliability") == "reliable":
        quality = "reliable"
    else:
        quality = "needs_review"
    return {
        **reading,
        "age_hours": round(age_hours, 1),
        "freshness": "stale" if stale else "current",
        "unit_compatible": compatible,
        "quality_status": quality,
    }


def trend_summary(points: list[dict]) -> dict | None:
    if len(points) < 2:
        return None
    latest, previous = points[-1], points[-2]
    if normalized_unit(latest.get("unit")) != normalized_unit(previous.get("unit")):
        return None
    delta = latest["value"] - previous["value"]
    tolerance = max(abs(previous["value"]) * 0.02, 0.01)
    direction = "steady" if abs(delta) <= tolerance else ("rising" if delta > 0 else "falling")
    return {
        "direction": direction,
        "change": round(delta, 2),
        "unit": latest.get("unit"),
        "from_timestamp": previous["timestamp"],
        "to_timestamp": latest["timestamp"],
    }


def crop_stage_advisory(latest: dict, context: dict, weather: dict) -> dict | None:
    crop_type = (context.get("crop_type") or "").strip()
    growth_stage = (context.get("growth_stage") or "").strip()
    if not crop_type or not growth_stage:
        return None

    group = crop_group(crop_type)
    stage = growth_stage.lower()
    moisture = latest.get("moisture")
    moisture_value = (
        moisture.get("value")
        if moisture and moisture.get("unit_compatible", True) and moisture.get("quality_status") not in ("stale", "unusable")
        else None
    )
    rain = weather.get("rain_next_24h_mm") if weather.get("usable_for_advice") else None
    evidence_parts = [f"Crop profile: {crop_type} · {growth_stage}."]
    if moisture_value is not None:
        evidence_parts.append(f"Soil moisture: {moisture_value:g}%.")
    if rain is not None:
        evidence_parts.append(f"Expected rain in 24 hours: {rain:g} mm.")

    priority = "normal"
    uncertainty = "Confirm soil moisture at root depth; field type, soil texture and irrigation method can change the action."

    if group == "rice":
        uncertainty = "Paddy and upland rice need different water management; confirm the production system and field drainage."
        if stage == "flowering":
            priority = "high"
            message = "Rice at flowering is highly sensitive to water stress."
            action = "Keep water available; check the rice field now and irrigate if rain is insufficient"
        elif stage in ("seedling", "vegetative", "fruiting / grain filling"):
            priority = "high" if moisture_value is not None and moisture_value < 20 else "normal"
            message = f"Rice at {growth_stage.lower()} has a high water need."
            action = "Keep paddy soil moist or saturated; use the moisture reading and rain before irrigating"
        elif stage == "land preparation":
            message = "Rice land preparation may require wet or saturated soil."
            action = "Confirm whether this is paddy or upland rice before adding water"
        elif stage == "maturity":
            message = "Rice at maturity needs less irrigation than during flowering and grain filling."
            action = "Confirm harvest timing and reduce or drain water near harvest"
        else:
            message = f"Rice at {growth_stage.lower()} needs close water monitoring."
            action = "Check field moisture and expected rain before irrigating"
    elif group == "potato":
        uncertainty = "Potato response also depends on soil drainage, rooting depth, variety and time remaining before harvest."
        if stage in ("flowering", "fruiting / grain filling"):
            priority = "high" if moisture_value is not None and moisture_value < 20 else "normal"
            message = "Potatoes at tuber initiation or bulking are sensitive to water shortage."
            action = "Keep root-zone moisture even; irrigate if dry, but avoid waterlogging"
        elif stage == "maturity":
            message = "Potatoes at maturity need less water than during tuber formation."
            action = "Reduce irrigation toward harvest and avoid leaving the soil wet"
        elif stage in ("germination", "seedling", "vegetative"):
            message = f"Potatoes at {growth_stage.lower()} need steady, well-drained moisture."
            action = "Check the root zone; irrigate if dry and avoid waterlogging"
        else:
            message = f"Potato water needs change at {growth_stage.lower()}."
            action = "Check root-zone moisture before irrigating"
    else:
        if stage in ("germination", "seedling", "flowering", "fruiting / grain filling"):
            priority = "high" if moisture_value is not None and moisture_value < 20 else "normal"
            message = f"{crop_type} at {growth_stage.lower()} needs close water monitoring."
            action = "Check the root zone and expected rain before irrigating"
        elif stage == "maturity":
            message = f"{crop_type} water need may fall as the crop reaches maturity."
            action = "Confirm harvest timing before adding more irrigation"
        else:
            message = f"Water advice now uses the {growth_stage.lower()} stage of {crop_type}."
            action = "Keep monitoring soil moisture and rain"

    return {
        "priority": priority,
        "title": f"According to {crop_type} · {growth_stage}",
        "message": message,
        "evidence": " ".join(evidence_parts),
        "uncertainty": uncertainty,
        "action": action,
    }


def reading_evidence(label: str, reading: dict, trend: dict | None = None) -> str:
    parts = [
        f"{label}: {reading['value']:g} {reading.get('unit') or ''}",
        f"source: {reading.get('source', 'unknown')}",
        f"measured: {reading['timestamp']}",
        f"quality: {reading.get('quality_status', 'needs review').replace('_', ' ')}",
    ]
    if trend:
        parts.append(f"trend: {trend['direction']} ({trend['change']:+g} {trend['unit']})")
    if reading.get("note"):
        parts.append(f"note: {reading['note']}")
    return "; ".join(parts) + "."


def normalize_sensor(sensor: Sensor) -> str | None:
    text = f"{sensor.sensor_type} {sensor.sensor_key} {sensor.name}".lower()
    if "nitrogen" in text or text.strip().startswith("n "):
        return "nitrogen"
    if "phosph" in text or "phosphate" in text:
        return "phosphorus"
    if "potassium" in text or "potash" in text:
        return "potassium"
    if "moist" in text:
        return "moisture"
    if "temp" in text:
        return "temperature"
    if "ph" in text:
        return "ph"
    return None


def weather_context(db: Session, field: FarmField) -> dict:
    farm = field.farm
    if farm.latitude is None or farm.longitude is None:
        return {"available": False, "note": "The farm has no exact weather coordinates."}
    key = f"weather:{farm.latitude:.3f}:{farm.longitude:.3f}"
    cached = db.scalar(select(WeatherCache).where(WeatherCache.cache_key == key).order_by(WeatherCache.created_at.desc()))
    if not cached:
        return {"available": False, "note": "Open Weather Intelligence for this farm to add weather evidence."}
    payload = json.loads(cached.payload_json)
    hourly = payload.get("hourly", {})
    now_kigali = datetime.now(KIGALI_TZ)
    times = hourly.get("time") or []
    future_indexes = []
    for index, value in enumerate(times):
        try:
            moment = datetime.fromisoformat(value).replace(tzinfo=KIGALI_TZ)
        except (TypeError, ValueError):
            continue
        if now_kigali <= moment < now_kigali + timedelta(hours=24):
            future_indexes.append(index)
    precipitation = hourly.get("precipitation") or []
    probabilities = hourly.get("precipitation_probability") or []
    rain = sum(float(precipitation[index] or 0) for index in future_indexes if index < len(precipitation))
    probability = max(
        [float(probabilities[index] or 0) for index in future_indexes if index < len(probabilities)],
        default=0,
    )
    stored_at = utc_datetime(cached.created_at)
    age_hours = max(0.0, (datetime.now(timezone.utc) - stored_at).total_seconds() / 3600)
    usable = bool(future_indexes) and age_hours <= 6
    return {
        "available": True,
        "usable_for_advice": usable,
        "rain_next_24h_mm": round(rain, 1),
        "rain_probability": round(probability),
        "observed_at": cached.created_at.isoformat(),
        "age_hours": round(age_hours, 1),
        "note": (
            "Current modelled forecast from Weather Intelligence."
            if usable else
            "Weather data is old or has no future hours; refresh Weather Intelligence before using it for irrigation."
        ),
    }


def advisories(latest: dict, context: dict, weather: dict, trends: dict[str, dict | None]) -> list[dict]:
    items: list[dict] = []
    crop_type = (context.get("crop_type") or "").strip()
    growth_stage = (context.get("growth_stage") or "").strip()
    group = crop_group(crop_type)
    stage = growth_stage.lower()
    stage_advice = crop_stage_advisory(latest, context, weather)
    if stage_advice:
        items.append(stage_advice)

    for kind in MEASUREMENTS:
        reading = latest.get(kind)
        label = LABELS[kind]
        if not reading:
            action = "Add a laboratory result" if kind in ("nitrogen", "phosphorus", "potassium", "ph") else "Add a field reading"
            items.append({
                "priority": "high", "title": f"According to {label}",
                "message": f"No reading yet (— {DEFAULT_UNITS[kind]}).",
                "evidence": f"{label} has not been measured for this field.",
                "uncertainty": "A condition cannot be identified without a reading.",
                "action": action,
            })
            continue

        value = reading["value"]
        unit = reading.get("unit") or DEFAULT_UNITS[kind]
        shown = f"{value:g} {unit}"
        trend = trends.get(kind)
        priority = "normal"
        message = f"The latest reading is {shown}."
        action = "Keep monitoring"
        uncertainty = "The best range depends on the crop, growth stage, soil and measurement method."

        if not reading.get("unit_compatible", True):
            priority = "high"
            message = f"{label} uses an unsupported unit: {unit}."
            action = f"Record {label.lower()} using {DEFAULT_UNITS[kind]}"
            uncertainty = "This value is stored, but it is excluded from agronomic interpretation until its unit is corrected."
        elif reading.get("freshness") == "stale":
            priority = "high"
            age_days = reading.get("age_hours", 0) / 24
            message = f"{label} is {shown}, but the reading is {age_days:.0f} days old."
            action = "Take a new reading before making a current field decision"
            uncertainty = "Old readings describe past conditions and may not represent the field now."
        elif kind in ("nitrogen", "phosphorus", "potassium"):
            if reading.get("quality_status") not in ("verified", "reliable") or reading["source"] == "device":
                priority = "high"
                message = f"{label} is {shown}, but it cannot support a fertilizer decision yet."
                action = "Confirm with a laboratory before applying fertilizer"
            else:
                message = f"{label} is {shown} from a reliable {reading['source']} result."
                action = "Use the laboratory's method and sufficiency range for this crop"
            uncertainty = "Nutrient values are not labelled low or high without the extraction method, sampling depth and a locally validated crop range."
        elif kind == "moisture" and unit == "%":
            rain = weather.get("rain_next_24h_mm") if weather.get("usable_for_advice") else None
            rain_probability = weather.get("rain_probability", 0) if weather.get("usable_for_advice") else 0
            if value < 20:
                priority = "high"
                trend_words = " and is falling" if trend and trend["direction"] == "falling" else ""
                message = f"Soil moisture is {shown}{trend_words}. This may be dry."
                if group == "rice" and stage != "maturity":
                    action = "Check the rice field now; irrigate if the root zone is dry and rain is insufficient"
                elif group == "potato" and stage == "maturity":
                    action = "Check whether the crop is still active before irrigating near harvest"
                elif group == "potato":
                    action = "Check the potato root zone; irrigate if dry, but avoid waterlogging"
                else:
                    action = "Check the root zone; irrigate only if the soil is dry"
                if rain is not None and rain >= 3 and rain_probability >= 50:
                    crop_name = crop_type or "crop"
                    action = f"Forecast: {rain:g} mm with {rain_probability:g}% chance; check the {crop_name} root zone before irrigating"
            elif value > 70:
                priority = "high"
                if group == "rice" and stage != "maturity":
                    message = f"Soil moisture is {shown}. This may suit paddy rice, but not upland rice."
                    action = "Check the rice production system, water depth and drainage before adding water"
                elif group == "potato":
                    message = f"Soil moisture is {shown}. It looks high for potatoes."
                    action = "Pause irrigation and check drainage around the roots and tubers"
                else:
                    message = f"Soil moisture is {shown}. It looks high."
                    action = "Pause irrigation and check drainage"
            else:
                direction = f" and {trend['direction']}" if trend else ""
                message = f"Soil moisture is {shown}{direction}. No automatic irrigation trigger is active."
            uncertainty = "A percentage is only comparable to field limits when the sensor is calibrated for its installation depth and soil texture."
        elif kind == "temperature" and normalized_unit(unit) in ("°c", "c", "celsius"):
            if group == "potato" and value > 25:
                priority = "high"
                message = f"Soil temperature is {shown}. This is warm for potatoes."
                action = "Check root-zone moisture and canopy cover; irrigate only if the soil is dry"
            elif value > 35:
                priority = "high"
                message = f"Soil temperature is {shown}. Heat stress risk is elevated."
                action = "Check moisture and crop stress now; consider mulch or shade where appropriate"
            elif value > 30:
                priority = "high" if stage in ("germination", "seedling", "flowering") else "normal"
                message = f"Soil temperature is {shown}. Watch for heat and drying."
                action = "Check moisture; irrigate only if dry, and consider mulch"
            elif value < 10:
                priority = "high"
                message = f"Soil temperature is {shown}. It is low."
                action = "Protect young plants and monitor germination"
            else:
                direction = f" and {trend['direction']}" if trend else ""
                message = f"Soil temperature is {shown}{direction}."
                action = "Keep monitoring temperature with moisture and crop stage"
            uncertainty = "Temperature needs vary by crop, growth stage, depth and time of day."
        elif kind == "ph":
            target = CROP_PH_RANGES.get(group)
            if target and value < target[0]:
                priority = "high"
                message = f"Soil pH is {value:g}, below the FAO reference range of {target[0]:g}–{target[1]:g} for {crop_type}."
                action = "Confirm with a laboratory before choosing lime or another amendment"
            elif target and value > target[1]:
                priority = "high"
                message = f"Soil pH is {value:g}, above the FAO reference range of {target[0]:g}–{target[1]:g} for {crop_type}."
                action = "Ask an agronomist before choosing an amendment"
            elif target:
                message = f"Soil pH is {value:g}, within the FAO reference range of {target[0]:g}–{target[1]:g} for {crop_type}."
                action = "Keep monitoring; do not amend pH from this result alone"
            elif value < 5.5:
                priority = "high"
                message = f"Soil pH is {value:g}. It may be acidic for many crops."
                action = "Select the crop and confirm with a laboratory before choosing lime"
            elif value > 7.5:
                priority = "high"
                message = f"Soil pH is {value:g}. It may be alkaline for many crops."
                action = "Select the crop and ask an agronomist before choosing an amendment"
            else:
                message = f"Soil pH is {value:g}; no crop-specific range is available for {crop_type or 'this field'}."
                action = "Use a crop-specific laboratory interpretation"
            uncertainty = "The reference range is screening guidance; amendment choice and rate require buffer pH, soil properties and a representative laboratory sample."

        items.append({
            "priority": priority, "title": f"According to {label}", "message": message,
            "evidence": reading_evidence(label, reading, trend),
            "uncertainty": uncertainty, "action": action,
        })

    moisture = latest.get("moisture")
    temperature = latest.get("temperature")
    ph = latest.get("ph")
    rain = weather.get("rain_next_24h_mm") if weather.get("usable_for_advice") else None
    if (
        moisture and temperature
        and moisture.get("quality_status") not in ("stale", "unusable")
        and temperature.get("quality_status") not in ("stale", "unusable")
        and moisture.get("unit_compatible") and temperature.get("unit_compatible")
        and moisture["value"] < 25 and temperature["value"] > 30
    ):
        items.append({
            "priority": "high", "title": "Combined heat and moisture signal",
            "message": f"Soil is warm ({temperature['value']:g} {temperature['unit']}) and moisture is low ({moisture['value']:g}%).",
            "evidence": "Two current field measurements point to faster drying and possible crop stress.",
            "uncertainty": "Confirm both sensors at root depth and inspect plants before acting.",
            "action": "Inspect the root zone now; irrigate only if it is dry",
        })
    if (
        moisture and moisture.get("quality_status") not in ("stale", "unusable")
        and moisture.get("unit_compatible") and moisture["value"] > 70
        and rain is not None and rain >= 5
    ):
        items.append({
            "priority": "high", "title": "Combined wet-soil and rain signal",
            "message": f"Soil moisture is {moisture['value']:g}% and {rain:g} mm rain is modelled in the next 24 hours.",
            "evidence": "A current soil reading and a usable cached forecast both indicate additional wetness.",
            "uncertainty": "Forecast rain may miss the field, and drainage differs across the plot.",
            "action": "Pause irrigation and inspect drainage, especially in low areas",
        })
    if ph and ph.get("unit_compatible") and ph.get("quality_status") not in ("stale", "unusable"):
        target = CROP_PH_RANGES.get(group)
        if target and not target[0] <= ph["value"] <= target[1] and any(latest.get(name) for name in ("nitrogen", "phosphorus", "potassium")):
            items.append({
                "priority": "high", "title": "pH can affect nutrient availability",
                "message": f"The pH result ({ph['value']:g}) is outside the crop reference range while nutrient readings are also present.",
                "evidence": f"Crop: {crop_type}; growth stage: {growth_stage}; pH reference: {target[0]:g}–{target[1]:g}.",
                "uncertainty": "This does not identify a deficiency or calculate an amendment rate.",
                "action": "Interpret the laboratory pH and nutrient results together before fertilizing",
            })

    if not context.get("crop_type") or not context.get("growth_stage"):
        items.append({
            "priority": "high", "title": "According to the crop profile",
            "message": "Crop or growth stage is missing.",
            "evidence": "Crop needs change during the season.",
            "uncertainty": "Soil advice stays general until the crop profile is complete.",
            "action": "Select the crop and growth stage",
        })
    return sorted(items, key=lambda item: 0 if item["priority"] == "high" else 1)


def soil_dashboard(db: Session, field: FarmField, owner_id: int) -> dict:
    now = datetime.now(timezone.utc)
    manual = db.scalars(select(SoilReading).where(SoilReading.field_id == field.id, SoilReading.owner_id == owner_id).order_by(SoilReading.measured_at.desc())).all()
    devices = db.scalars(select(Device).where(Device.field_id == field.id, Device.owner_id == owner_id).options(selectinload(Device.sensors).selectinload(Sensor.readings))).all()
    points: dict[str, list[dict]] = {name: [] for name in MEASUREMENTS}
    for item in manual:
        if item.measurement_type in points:
            points[item.measurement_type].append({
                "id": f"soil-{item.id}", "value": item.value, "unit": item.unit, "source": item.source,
                "calibration_status": item.calibration_status, "reliability": item.reliability,
                "status": "recorded", "timestamp": item.measured_at.isoformat(), "note": item.note,
            })
    for device in devices:
        for sensor in device.sensors:
            kind = normalize_sensor(sensor)
            if not kind:
                continue
            history = sorted(sensor.readings, key=lambda value: value.recorded_at, reverse=True)
            for reading in history[:30]:
                points[kind].append({
                    "id": f"sensor-{reading.id}", "value": reading.value, "unit": sensor.unit or "raw", "source": "device",
                    "calibration_status": "unknown", "reliability": "needs_review",
                    "status": device.status, "timestamp": reading.recorded_at.isoformat(), "note": f"Reported by {device.name}",
                })
    latest = {}
    measurements = []
    trends: dict[str, dict | None] = {}
    for kind in MEASUREMENTS:
        ordered = sorted(
            (decorate_reading(kind, item, now) for item in points[kind]),
            key=lambda item: item["timestamp"],
            reverse=True,
        )
        current = ordered[0] if ordered else None
        if current:
            latest[kind] = current
        chronological = list(reversed(ordered[:20]))
        comparable = [
            item for item in chronological
            if current
            and normalized_unit(item.get("unit")) == normalized_unit(current.get("unit"))
            and item.get("quality_status") != "unusable"
        ]
        trend = trend_summary(comparable)
        trends[kind] = trend
        measurements.append({
            "type": kind,
            "label": LABELS[kind],
            "latest": current,
            "trend": comparable,
            "trend_summary": trend,
        })
    context = {"crop_type": field.soil_context.crop_type if field.soil_context else field.crop_note, "growth_stage": field.soil_context.growth_stage if field.soil_context else None}
    weather = weather_context(db, field)
    reliable = sum(1 for item in latest.values() if item["quality_status"] in ("verified", "reliable"))
    current = sum(1 for item in latest.values() if item["freshness"] == "current")
    compatible = sum(1 for item in latest.values() if item["unit_compatible"])
    needs_review = sum(1 for item in latest.values() if item["quality_status"] in ("needs_review", "unusable", "stale"))
    available = len(latest)
    completeness_score = available / len(MEASUREMENTS)
    quality_score = reliable / available if available else 0
    freshness_score = current / available if available else 0
    unit_score = compatible / available if available else 0
    profile_score = 1 if context.get("crop_type") and context.get("growth_stage") else 0
    weather_score = 1 if weather.get("usable_for_advice") else 0
    score = round(100 * (
        0.30 * completeness_score
        + 0.25 * quality_score
        + 0.15 * freshness_score
        + 0.10 * unit_score
        + 0.10 * profile_score
        + 0.10 * weather_score
    ))
    readiness = "high" if score >= 80 else ("medium" if score >= 50 else "low")
    checks = []
    checks.append({
        "status": "good" if available == len(MEASUREMENTS) else "warning",
        "label": f"{available} of {len(MEASUREMENTS)} measurements available",
    })
    checks.append({
        "status": "good" if reliable == available and available else "warning",
        "label": f"{reliable} measurements verified or calibrated",
    })
    if available:
        checks.append({
            "status": "good" if current == available else "warning",
            "label": f"{current} current · {available - current} stale",
        })
    checks.append({
        "status": "good" if weather.get("usable_for_advice") else "warning",
        "label": "Weather is current" if weather.get("usable_for_advice") else "Weather needs refresh",
    })
    checks.append({
        "status": "good" if context.get("crop_type") and context.get("growth_stage") else "warning",
        "label": "Crop and growth stage selected" if context.get("crop_type") and context.get("growth_stage") else "Crop profile incomplete",
    })
    return {
        "field": {"id": field.id, "name": field.name, "farm_id": field.farm_id, "farm_name": field.farm.name},
        "context": context, "measurements": measurements, "weather": weather,
        "summary": {
            "available": available,
            "missing": len(MEASUREMENTS) - available,
            "reliable": reliable,
            "current": current,
            "needs_review": needs_review,
            "device_count": len(devices),
        },
        "data_quality": {"score": score, "status": readiness, "checks": checks},
        "advisories": advisories(latest, context, weather, trends),
        "safety_note": "This advisory supports monitoring. It does not replace a representative laboratory soil test, a calibrated sensor programme or a qualified agronomist.",
        "generated_at": now.isoformat(),
    }
