def farm_payload():
    return {"name": "Water Farm", "province": "ignored", "district": "ignored", "sector": "ignored", "cell": "ignored", "village": "ignored", "province_code": 4, "district_code": 403, "sector_code": "040310", "cell_code": 4031001, "village_code": 403100101, "latitude": -1.499, "longitude": 29.634}


def create_field_and_device(client, auth):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    field_id = client.post(f"/api/v1/farms/{farm_id}/fields", headers=auth, json={"name": "Irrigation plot", "side_a": 20, "side_b": 10, "side_c": 20, "side_d": 10, "side_unit": "m"}).json()["id"]
    device = client.post("/api/v1/devices", headers=auth, json={
        "field_id": field_id, "name": "Field water monitor", "device_uid": "WATER-001", "port": "COM9",
        "sensors": [
            {"key": "ultrasonic_distance", "name": "Tank ultrasonic", "type": "ultrasonic", "unit": "cm"},
            {"key": "soil_moisture", "name": "Soil moisture", "type": "soil_moisture", "unit": "%"},
        ],
    }).json()
    return field_id, device


def test_tank_uses_linked_ultrasonic_reading_and_irrigation_status(client, auth, monkeypatch):
    field_id, device = create_field_and_device(client, auth)
    ultrasonic = next(item for item in device["sensors"] if item["key"] == "ultrasonic_distance")
    created = client.post(f"/api/v1/fields/{field_id}/water-sources", headers=auth, json={
        "name": "Main tank", "source_type": "tank", "capacity_liters": 1000,
        "tank_height_cm": 200, "sensor_id": ultrasonic["id"], "is_primary": True,
    })
    assert created.status_code == 201
    assert created.json()["is_primary"] is True

    credentials = client.post(f"/api/v1/iot/devices/{device['id']}/credentials", headers=auth).json()
    device_headers = {"X-Device-ID": credentials["device_uid"], "X-Device-Key": credentials["device_key"]}
    reading = client.post("/api/v1/iot/readings", headers=device_headers, json={"readings": [
        {"key": "ultrasonic_distance", "value": 50, "unit": "cm"},
        {"key": "soil_moisture", "value": 20, "unit": "%"},
    ]})
    assert reading.status_code == 200

    dashboard = client.get(f"/api/v1/fields/{field_id}/water-sources", headers=auth).json()
    level = dashboard["sources"][0]["latest_level"]
    assert level["remaining_percent"] == 75.0
    assert level["remaining_liters"] == 750.0
    assert level["measurement_method"] == "ultrasonic_distance"

    monkeypatch.setattr("app.services.irrigation.weather_dashboard", lambda *args, **kwargs: {
        "hourly": {"precipitation": [0] * 24, "precipitation_probability": [5] * 24},
        "current": {"temperature_2m": 24}, "provider": "Test", "generated_at": "now",
    })
    status = client.get(f"/api/v1/irrigation/status?field_id={field_id}", headers=auth).json()
    assert status["decision"] == "recommended"
    assert status["measurements"]["tank_level"]["value"] == 75.0
    assert status["measurements"]["tank_level"]["remaining_liters"] == 750.0
    assert status["water_source"]["name"] == "Main tank"


def test_non_tank_primary_source_does_not_invent_a_tank_level(client, auth, monkeypatch):
    field_id, device = create_field_and_device(client, auth)
    credentials = client.post(f"/api/v1/iot/devices/{device['id']}/credentials", headers=auth).json()
    client.post("/api/v1/iot/readings", headers={"X-Device-ID": credentials["device_uid"], "X-Device-Key": credentials["device_key"]}, json={"readings": [{"key": "soil_moisture", "value": 20, "unit": "%"}]})
    source = client.post(f"/api/v1/fields/{field_id}/water-sources", headers=auth, json={"name": "Community borehole", "source_type": "borehole"})
    assert source.status_code == 201
    monkeypatch.setattr("app.services.irrigation.weather_dashboard", lambda *args, **kwargs: {"hourly": {"precipitation": [0] * 24, "precipitation_probability": [0] * 24}, "current": {}, "provider": "Test", "generated_at": "now"})
    result = client.get(f"/api/v1/irrigation/status?field_id={field_id}", headers=auth).json()
    assert result["measurements"]["tank_level"] is None
    assert result["water_source"]["source_type"] == "borehole"
    assert result["decision"] == "recommended"
    assert any("borehole" in reason for reason in result["reasons"])


def test_water_source_rejects_sensor_from_another_field(client, auth):
    field_id, device = create_field_and_device(client, auth)
    farm_id = client.get("/api/v1/farms", headers=auth).json()[0]["id"]
    other_field = client.post(f"/api/v1/farms/{farm_id}/fields", headers=auth, json={"name": "Other plot", "side_a": 10, "side_b": 10, "side_c": 10, "side_d": 10, "side_unit": "m"}).json()["id"]
    sensor_id = next(item["id"] for item in device["sensors"] if item["key"] == "ultrasonic_distance")
    response = client.post(f"/api/v1/fields/{other_field}/water-sources", headers=auth, json={"name": "Wrong sensor", "source_type": "tank", "sensor_id": sensor_id})
    assert response.status_code == 422
