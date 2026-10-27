import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Device,
    FarmField,
    IrrigationCommand,
    IrrigationConfig,
    Sensor,
    SensorReading,
    SoilReading,
)
from app.services.weather import weather_dashboard
from app.services.water_sources import latest_level, primary_source, source_view


SENSOR_RANGES = {
    "soil_moisture": (0, 100), "moisture": (0, 100),
    "temperature": (-20, 80), "air_temperature": (-20, 80), "soil_temperature": (-10, 70),
    "humidity": (0, 100), "tank_level": (0, 100), "tank_level_percent": (0, 100),
    "water_level": (0, 100), "flow_rate": (0, 1000), "rainfall": (0, 1000),
    "ultrasonic_distance": (0, 100000), "tank_distance": (0, 100000), "distance": (0, 100000),
    "nitrogen": (0, 10000), "phosphorus": (0, 10000), "potassium": (0, 10000), "ph": (0, 14),
}
MOISTURE_KEYS = {"soil_moisture", "moisture"}
TANK_KEYS = {"tank_level", "tank_level_percent", "water_level"}
TEMPERATURE_KEYS = {"temperature", "air_temperature", "soil_temperature"}
RAIN_KEYS = {"rainfall", "rainfall_24h"}
FLOW_KEYS = {"flow_rate", "water_flow", "flow"}
COMMAND_TTL_MINUTES = 5


def _utc(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def hash_device_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def provision_device_key(device: Device) -> str:
    key = secrets.token_urlsafe(32)
    device.api_key_hash = hash_device_key(key)
    return key


def authenticate_device(db: Session, device_uid: str, api_key: str) -> Device:
    device = db.scalar(
        select(Device).where(Device.device_uid == device_uid).options(selectinload(Device.sensors), selectinload(Device.field))
    )
    if not device or not device.api_key_hash or not hmac.compare_digest(device.api_key_hash, hash_device_key(api_key)):
        raise HTTPException(status_code=401, detail="Invalid device credentials")
    return device


def _valid_sensor_value(key: str, value: float) -> bool:
    limits = SENSOR_RANGES.get(key.casefold())
    return not limits or limits[0] <= value <= limits[1]


def ingest_readings(db: Session, device: Device, payload) -> dict:
    sensors = {sensor.sensor_key.casefold(): sensor for sensor in device.sensors}
    accepted = rejected = simulated = 0
    now = datetime.now(timezone.utc)
    for item in payload.readings:
        sensor = sensors.get(item.key.casefold())
        if not sensor:
            rejected += 1
            continue
        recorded_at = _utc(item.recorded_at)
        valid = item.valid and _valid_sensor_value(item.key, item.value) and recorded_at <= now + timedelta(minutes=5)
        db.add(SensorReading(sensor_id=sensor.id, value=item.value, recorded_at=recorded_at, valid=valid, simulated=item.simulated))
        if item.simulated:
            simulated += 1
        if not valid:
            rejected += 1
            continue
        sensor.latest_value = item.value
        sensor.last_read_at = recorded_at
        accepted += 1
        measurement = {
            "soil_moisture": "moisture", "moisture": "moisture", "soil_temperature": "temperature",
            "nitrogen": "nitrogen", "phosphorus": "phosphorus", "potassium": "potassium", "ph": "ph",
        }.get(item.key.casefold())
        if measurement and device.field_id:
            db.add(SoilReading(
                owner_id=device.owner_id, field_id=device.field_id, measurement_type=measurement,
                value=item.value, unit=item.unit or sensor.unit or "unknown", source="sensor",
                calibration_status="unknown", reliability="needs_review",
                note="SIMULATED device reading" if item.simulated else f"Received from {device.name}", measured_at=recorded_at,
            ))
    device.last_seen_at = now
    device.status = "connected"
    if payload.firmware_version:
        device.firmware_version = payload.firmware_version
    db.commit()
    return {"accepted": accepted, "rejected": rejected, "simulated": simulated, "received_at": now.isoformat()}


def get_or_create_config(db: Session, field_id: int) -> IrrigationConfig:
    config = db.scalar(select(IrrigationConfig).where(IrrigationConfig.field_id == field_id))
    if not config:
        config = IrrigationConfig(field_id=field_id)
        db.add(config)
        db.flush()
    return config


def config_view(config: IrrigationConfig) -> dict:
    return {
        "mode": config.mode, "safety_validated": config.safety_validated,
        "remote_control_enabled": config.remote_control_enabled, "emergency_stop": config.emergency_stop,
        "max_pump_runtime_seconds": config.max_pump_runtime_seconds, "cooldown_minutes": config.cooldown_minutes,
        "min_tank_percent": config.min_tank_percent, "max_reading_age_minutes": config.max_reading_age_minutes,
        "moisture_trigger_percent": config.moisture_trigger_percent,
    }


def _latest_measurements(db: Session, field_id: int) -> dict[str, dict]:
    rows = db.execute(
        select(Sensor, SensorReading, Device)
        .join(SensorReading, SensorReading.sensor_id == Sensor.id)
        .join(Device, Device.id == Sensor.device_id)
        .where(Device.field_id == field_id, SensorReading.valid.is_(True))
        .order_by(SensorReading.recorded_at.desc())
    ).all()
    latest = {}
    for sensor, reading, device in rows:
        key = sensor.sensor_key.casefold()
        if key not in latest:
            latest[key] = {
                "key": key, "name": sensor.name, "value": reading.value, "unit": sensor.unit,
                "recorded_at": _utc(reading.recorded_at).isoformat(), "simulated": reading.simulated,
                "device_id": device.id, "device_name": device.name,
            }
    return latest


def _first(latest: dict, keys: set[str]) -> dict | None:
    return next((latest[key] for key in keys if key in latest), None)


def _moisture_threshold(field: FarmField, config: IrrigationConfig) -> tuple[float, str]:
    if config.moisture_trigger_percent is not None:
        return config.moisture_trigger_percent, "configured field trigger"
    crop = ((field.soil_context.crop_type if field.soil_context else None) or field.crop_note or "").casefold()
    thresholds = {"paddy rice": 50, "rice": 50, "banana": 40, "irish potato": 35, "potato": 35, "maize": 32, "beans": 30, "cassava": 25}
    base = next((value for name, value in thresholds.items() if name in crop), 35)
    stage = ((field.soil_context.growth_stage if field.soil_context else None) or "").casefold()
    if any(term in stage for term in ("establish", "flower", "tuber", "fruit")):
        base += 5
    elif any(term in stage for term in ("mature", "harvest")):
        base -= 5
    return float(base), "conservative crop/stage operational trigger"


def irrigation_status(db: Session, field: FarmField, include_weather: bool = True) -> dict:
    config = get_or_create_config(db, field.id)
    latest = _latest_measurements(db, field.id)
    moisture = _first(latest, MOISTURE_KEYS)
    water_source = primary_source(db, field.id)
    registered_level = latest_level(db, water_source) if water_source and water_source.source_type == "tank" else None
    tank = ({
        "key": "registered_tank_level",
        "name": water_source.name,
        "value": registered_level["remaining_percent"],
        "unit": "%",
        "recorded_at": registered_level["recorded_at"],
        "simulated": registered_level["simulated"],
        "device_id": registered_level["device_id"],
        "sensor_id": registered_level["sensor_id"],
        "measurement_method": registered_level["measurement_method"],
        "remaining_liters": registered_level["remaining_liters"],
    } if registered_level and registered_level["remaining_percent"] is not None else None)
    if water_source is None:
        tank = _first(latest, TANK_KEYS)
    temperature = _first(latest, TEMPERATURE_KEYS)
    recent_rain = _first(latest, RAIN_KEYS)
    flow = _first(latest, FLOW_KEYS)
    threshold, threshold_source = _moisture_threshold(field, config)
    now = datetime.now(timezone.utc)
    reasons = []
    missing = []
    stale = []
    required_readings = [("soil moisture", moisture)]
    if water_source is None or water_source.source_type == "tank":
        required_readings.append(("tank level", tank))
    for label, reading in required_readings:
        if not reading:
            missing.append(label)
        elif now - _utc(datetime.fromisoformat(reading["recorded_at"])) > timedelta(minutes=config.max_reading_age_minutes):
            stale.append(label)

    weather = None
    weather_error = None
    if include_weather and field.farm.latitude is not None and field.farm.longitude is not None:
        try:
            raw = weather_dashboard(db, field.farm.latitude, field.farm.longitude, field.farm.name, "saved farm")
            hourly = raw.get("hourly", {})
            rain_values = [float(value or 0) for value in (hourly.get("precipitation") or [])[:24]]
            probabilities = [float(value or 0) for value in (hourly.get("precipitation_probability") or [])[:24]]
            weather = {
                "rain_next_24h_mm": round(sum(rain_values), 1), "rain_probability_max": round(max(probabilities, default=0)),
                "temperature_c": raw.get("current", {}).get("temperature_2m"), "provider": raw.get("provider"),
                "generated_at": raw.get("generated_at"),
            }
        except HTTPException as exc:
            weather_error = exc.detail
    elif include_weather:
        weather_error = "Farm coordinates are unavailable"

    if config.emergency_stop:
        decision, title = "blocked", "Pump blocked by emergency stop"
        reasons.append("Emergency stop is active. Reset it only after checking the pump and field.")
    elif missing:
        decision, title = "uncertain", "More sensor data is needed"
        reasons.append(f"Missing required measurement(s): {', '.join(missing)}.")
    elif stale:
        decision, title = "uncertain", "Sensor readings are too old"
        reasons.append(f"Stale measurement(s): {', '.join(stale)}. Maximum age is {config.max_reading_age_minutes} minutes.")
    elif moisture.get("simulated") or (tank and tank.get("simulated")):
        decision, title = "uncertain", "Live measurements are required"
        reasons.append("Soil moisture or tank level is SIMULATED. A real pump command requires fresh, physical sensor readings.")
    elif tank and tank["value"] < config.min_tank_percent:
        decision, title = "blocked", "Not enough water in the tank"
        reasons.append(f"Tank level is {tank['value']:.1f}%; the safety minimum is {config.min_tank_percent:.1f}%.")
    elif moisture["value"] >= threshold:
        decision, title = "not_needed", "Irrigation is not currently needed"
        reasons.append(f"Soil moisture is {moisture['value']:.1f}%, above the {threshold:.1f}% {threshold_source}.")
    elif recent_rain and now - _utc(datetime.fromisoformat(recent_rain["recorded_at"])) <= timedelta(hours=24) and recent_rain["value"] >= 3:
        decision, title = "postpone", "Recent rainfall may still be supplying water"
        reasons.append(f"A recent field reading recorded {recent_rain['value']:.1f}{recent_rain.get('unit') or ' mm'} of rain within the last 24 hours.")
        reasons.append(f"Soil moisture is below the {threshold:.1f}% trigger, so inspect the root zone and measure again before starting the pump.")
    elif include_weather and weather is None:
        decision, title = "uncertain", "Weather check is unavailable"
        reasons.append("Soil is below the trigger, but the forecast could not be checked; inspect conditions before irrigating.")
    elif weather and (weather["rain_next_24h_mm"] >= 3 or weather["rain_probability_max"] >= 60):
        decision, title = "postpone", "Postpone irrigation and watch the rain"
        reasons.append(f"Forecast: {weather['rain_next_24h_mm']:.1f} mm rain and up to {weather['rain_probability_max']}% probability in 24 hours.")
        reasons.append(f"Soil moisture is {moisture['value']:.1f}%, below the {threshold:.1f}% trigger, so check again after the forecast period.")
    else:
        decision, title = "recommended", "Irrigation is recommended"
        reasons.append(f"Soil moisture is {moisture['value']:.1f}%, below the {threshold:.1f}% {threshold_source}.")
        if weather:
            reasons.append(f"Only {weather['rain_next_24h_mm']:.1f} mm rain is forecast in the next 24 hours (maximum probability {weather['rain_probability_max']}%).")
    if tank and decision not in ("blocked", "uncertain"):
        reasons.append(f"Tank level is {tank['value']:.1f}%, above the {config.min_tank_percent:.1f}% safety minimum.")
    if water_source and water_source.source_type != "tank":
        reasons.append(f"Primary irrigation source is {water_source.name} ({water_source.source_type}); tank-level safety does not apply. Confirm that this source can currently supply water.")
    if temperature and decision == "recommended":
        reasons.append(f"The latest temperature reading is {temperature['value']:.1f}{temperature.get('unit') or '°C'}; moisture and forecast evidence remain the decision triggers.")
    if recent_rain:
        reasons.append(f"The latest recorded rainfall input is {recent_rain['value']:.1f}{recent_rain.get('unit') or ' mm'}.")
    if flow:
        reasons.append(f"Latest water flow is {flow['value']:.1f}{flow.get('unit') or ''}; compare it with the pump's expected flow during operation.")
    if any(item and item.get("simulated") for item in (moisture, tank, temperature, recent_rain, flow)):
        reasons.append("At least one input is SIMULATED; do not treat this as a real pump instruction.")

    commands = db.scalars(select(IrrigationCommand).where(IrrigationCommand.field_id == field.id).order_by(IrrigationCommand.issued_at.desc()).limit(10)).all()
    db.commit()
    return {
        "decision": decision, "title": title, "reasons": reasons,
        "field": {"id": field.id, "name": field.name, "farm_name": field.farm.name, "crop": (field.soil_context.crop_type if field.soil_context else None) or field.crop_note, "growth_stage": field.soil_context.growth_stage if field.soil_context else None},
        "measurements": {"soil_moisture": moisture, "tank_level": tank, "temperature": temperature, "recent_rainfall": recent_rain, "flow_rate": flow},
        "water_source": source_view(db, water_source) if water_source else None,
        "weather": weather, "weather_error": weather_error,
        "threshold": {"soil_moisture_percent": threshold, "source": threshold_source},
        "config": config_view(config),
        "commands": [command_view(item) for item in commands],
        "generated_at": now.isoformat(),
        "uncertainty": "Low-cost sensors must be calibrated locally. This engine provides decision support and never guarantees crop response.",
    }


def command_view(item: IrrigationCommand) -> dict:
    expires_at = _utc(item.issued_at) + timedelta(minutes=COMMAND_TTL_MINUTES) if item.command == "start" else None
    return {
        "id": item.id, "field_id": item.field_id, "device_id": item.device_id, "command": item.command,
        "duration_seconds": item.duration_seconds, "status": item.status, "source": item.source,
        "simulated": item.simulated, "reasons": json.loads(item.reason_json), "execution_message": item.execution_message,
        "issued_at": _utc(item.issued_at).isoformat(), "executed_at": _utc(item.executed_at).isoformat() if item.executed_at else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


def pending_device_commands(db: Session, device: Device) -> list[dict]:
    """Return only commands that are still safe for this device to execute."""
    commands = db.scalars(
        select(IrrigationCommand)
        .where(IrrigationCommand.device_id == device.id, IrrigationCommand.status == "pending")
        .order_by(IrrigationCommand.issued_at)
    ).all()
    config = get_or_create_config(db, device.field_id) if device.field_id else None
    now = datetime.now(timezone.utc)
    available = []
    changed = False
    for command in commands:
        rejection = None
        if command.command == "start":
            if now - _utc(command.issued_at) > timedelta(minutes=COMMAND_TTL_MINUTES):
                rejection = "Start command expired before the device collected it; pump remains OFF"
            elif not config or config.emergency_stop:
                rejection = "Emergency stop is active; pump remains OFF"
            elif not config.remote_control_enabled or not device.remote_control_enabled:
                rejection = "Remote control permission was removed; pump remains OFF"
            elif command.source == "automatic" and (config.mode != "automatic" or not config.safety_validated):
                rejection = "Automatic mode is no longer safety-validated; pump remains OFF"
        if rejection:
            command.status = "rejected"
            command.execution_message = rejection
            command.executed_at = now
            changed = True
        else:
            available.append(command_view(command))
    if changed:
        db.commit()
    return available


def create_command(db: Session, field: FarmField, user_id: int | None, payload, source: str = "manual") -> dict:
    config = get_or_create_config(db, field.id)
    devices = db.scalars(select(Device).where(Device.field_id == field.id).options(selectinload(Device.sensors))).all()
    device = next((item for item in devices if any("relay" in sensor.sensor_key.casefold() or "pump" in sensor.sensor_key.casefold() or "relay" in sensor.sensor_type.casefold() for sensor in item.sensors)), None)
    if not device:
        raise HTTPException(status_code=409, detail="No pump relay is registered for this field")
    reasons = []
    if payload.command in ("stop", "emergency_stop"):
        if payload.command == "emergency_stop":
            config.emergency_stop = True
            reasons.append("Emergency stop requested by the farmer; pump must default OFF.")
        else:
            reasons.append("Stop commands are always allowed as a safe action.")
        duration = None
    else:
        if config.emergency_stop:
            raise HTTPException(status_code=409, detail="Emergency stop is active")
        if not config.remote_control_enabled or not device.remote_control_enabled:
            raise HTTPException(status_code=403, detail="Remote pump control is not enabled for both field and device")
        if config.mode == "automatic" and not config.safety_validated:
            raise HTTPException(status_code=409, detail="Automatic mode requires explicit safety validation")
        if source == "automatic" and (config.mode != "automatic" or not config.safety_validated):
            raise HTTPException(status_code=409, detail="Automatic irrigation is not enabled and safety-validated")
        decision = irrigation_status(db, field)
        if decision["decision"] in ("blocked", "uncertain"):
            raise HTTPException(status_code=409, detail=f"Pump start blocked: {decision['title']}")
        if source == "automatic" and decision["decision"] != "recommended":
            raise HTTPException(status_code=409, detail=f"Automatic start not needed: {decision['title']}")
        duration = payload.duration_seconds or min(300, config.max_pump_runtime_seconds)
        if duration > config.max_pump_runtime_seconds:
            raise HTTPException(status_code=422, detail=f"Maximum pump runtime is {config.max_pump_runtime_seconds} seconds")
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=config.cooldown_minutes)
        recent = db.scalar(select(IrrigationCommand).where(IrrigationCommand.field_id == field.id, IrrigationCommand.command == "start", IrrigationCommand.issued_at >= cutoff.replace(tzinfo=None)).order_by(IrrigationCommand.issued_at.desc()))
        if recent:
            raise HTTPException(status_code=409, detail=f"Pump cooldown is active for {config.cooldown_minutes} minutes")
        reasons.extend(decision["reasons"])
        if decision["decision"] != "recommended":
            reasons.append(f"Manual override recorded while decision was {decision['decision']}.")
    item = IrrigationCommand(
        field_id=field.id, device_id=device.id, requested_by_user_id=user_id, command=payload.command,
        duration_seconds=duration, source=source, simulated=payload.simulated, reason_json=json.dumps(reasons),
    )
    db.add(item)
    db.flush()
    db.commit()
    return command_view(item)
