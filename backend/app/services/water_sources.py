from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Device, FarmField, Sensor, SensorReading, WaterSource

SOURCE_TYPES = {"tank", "pond", "borehole", "river", "tap", "rainwater", "other"}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def is_level_sensor(sensor: Sensor) -> bool:
    text = f"{sensor.sensor_key} {sensor.name} {sensor.sensor_type}".casefold()
    return any(term in text for term in ("tank_level", "water_level", "ultrasonic", "distance", "water level", "tank level"))


def compatible_sensors(db: Session, field_id: int) -> list[dict]:
    sensors = db.scalars(
        select(Sensor)
        .join(Device, Device.id == Sensor.device_id)
        .where(Device.field_id == field_id)
        .options(selectinload(Sensor.device), selectinload(Sensor.water_source))
        .order_by(Device.name, Sensor.name)
    ).all()
    return [{
        "id": sensor.id,
        "name": sensor.name,
        "key": sensor.sensor_key,
        "sensor_type": sensor.sensor_type,
        "unit": sensor.unit,
        "device_id": sensor.device_id,
        "device_name": sensor.device.name,
        "available": sensor.water_source is None,
        "water_source_id": sensor.water_source.id if sensor.water_source else None,
    } for sensor in sensors if is_level_sensor(sensor)]


def validate_sensor(db: Session, field_id: int, sensor_id: int | None, source_id: int | None = None) -> Sensor | None:
    if sensor_id is None:
        return None
    sensor = db.scalar(
        select(Sensor)
        .join(Device, Device.id == Sensor.device_id)
        .where(Sensor.id == sensor_id, Device.field_id == field_id)
        .options(selectinload(Sensor.water_source))
    )
    if not sensor:
        raise HTTPException(status_code=422, detail="Select a sensor from a device assigned to this field")
    if not is_level_sensor(sensor):
        raise HTTPException(status_code=422, detail="Select a water-level, tank-level or ultrasonic distance sensor")
    if sensor.water_source and sensor.water_source.id != source_id:
        raise HTTPException(status_code=409, detail="This sensor is already linked to another water source")
    return sensor


def latest_level(db: Session, source: WaterSource) -> dict | None:
    if not source.sensor:
        return None
    reading = db.scalar(
        select(SensorReading)
        .where(SensorReading.sensor_id == source.sensor.id, SensorReading.valid.is_(True))
        .order_by(SensorReading.recorded_at.desc())
        .limit(1)
    )
    if not reading:
        return None
    sensor = source.sensor
    unit = (sensor.unit or "").strip().casefold()
    key_text = f"{sensor.sensor_key} {sensor.sensor_type}".casefold()
    percent = None
    method = None
    limitation = None
    if unit in {"%", "percent", "percentage"} or "percent" in key_text or (not unit and "level" in key_text and "distance" not in key_text and "ultrasonic" not in key_text):
        percent = max(0.0, min(100.0, float(reading.value)))
        method = "sensor_percent"
    elif unit in {"cm", "mm", "m"} or "distance" in key_text or "ultrasonic" in key_text:
        if source.tank_height_cm:
            distance_cm = float(reading.value) * ({"mm": 0.1, "m": 100.0}.get(unit, 1.0))
            percent = max(0.0, min(100.0, (source.tank_height_cm - distance_cm) / source.tank_height_cm * 100))
            method = "ultrasonic_distance"
            if distance_cm > source.tank_height_cm:
                limitation = "Distance exceeds the registered tank height; inspect sensor placement and tank height"
        else:
            limitation = "Register tank height to convert ultrasonic distance into remaining water"
    elif unit in {"l", "liter", "liters", "litre", "litres"} and source.capacity_liters:
        percent = max(0.0, min(100.0, float(reading.value) / source.capacity_liters * 100))
        method = "sensor_liters"
    else:
        limitation = "Sensor unit is not supported for remaining-water calculation"

    return {
        "sensor_id": sensor.id,
        "sensor_name": sensor.name,
        "device_id": sensor.device_id,
        "raw_value": reading.value,
        "raw_unit": sensor.unit,
        "recorded_at": _utc(reading.recorded_at).isoformat(),
        "simulated": reading.simulated,
        "remaining_percent": round(percent, 1) if percent is not None else None,
        "remaining_liters": round(source.capacity_liters * percent / 100, 1) if percent is not None and source.capacity_liters else None,
        "measurement_method": method,
        "limitation": limitation,
    }


def source_view(db: Session, source: WaterSource) -> dict:
    return {
        "id": source.id,
        "field_id": source.field_id,
        "name": source.name,
        "source_type": source.source_type,
        "capacity_liters": source.capacity_liters,
        "tank_height_cm": source.tank_height_cm,
        "sensor_id": source.sensor_id,
        "notes": source.notes,
        "is_primary": source.is_primary,
        "is_active": source.is_active,
        "latest_level": latest_level(db, source) if source.source_type == "tank" else None,
        "created_at": _utc(source.created_at).isoformat(),
        "updated_at": _utc(source.updated_at).isoformat(),
    }


def list_sources(db: Session, field_id: int) -> list[WaterSource]:
    return db.scalars(
        select(WaterSource)
        .where(WaterSource.field_id == field_id)
        .options(selectinload(WaterSource.sensor))
        .order_by(WaterSource.is_primary.desc(), WaterSource.created_at)
    ).all()


def set_primary(db: Session, field_id: int, source: WaterSource) -> None:
    for item in db.scalars(select(WaterSource).where(WaterSource.field_id == field_id, WaterSource.id != source.id)):
        item.is_primary = False
    source.is_primary = True


def primary_source(db: Session, field_id: int) -> WaterSource | None:
    sources = list_sources(db, field_id)
    active = [item for item in sources if item.is_active]
    return next((item for item in active if item.is_primary), active[0] if active else None)
