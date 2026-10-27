from datetime import datetime, timedelta, timezone

from app.db.models import Device, IrrigationCommand
from app.db.session import SessionLocal


def farm_payload():
    return {"name": "Hill Farm", "province": "ignored", "district": "ignored", "sector": "ignored", "cell": "ignored", "village": "ignored", "province_code": 4, "district_code": 403, "sector_code": "040310", "cell_code": 4031001, "village_code": 403100101, "latitude": -1.499, "longitude": 29.634}


def test_registration_and_owner_scoped_farm(client, auth):
    created = client.post("/api/v1/farms", headers=auth, json=farm_payload())
    assert created.status_code == 201
    assert created.json()["district"] == "Musanze"
    assert created.json()["village_code"] == 403100101
    assert len(client.get("/api/v1/farms", headers=auth).json()) == 1
    assert client.get("/api/v1/farms").status_code == 401


def test_farm_and_field_can_be_updated(client, auth):
    farm = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()
    updated_farm_payload = {**farm_payload(), "name": "Updated Hill Farm", "latitude": -1.5, "longitude": 29.63}
    updated_farm = client.put(f"/api/v1/farms/{farm['id']}", headers=auth, json=updated_farm_payload)
    assert updated_farm.status_code == 200
    assert updated_farm.json()["name"] == "Updated Hill Farm"
    assert updated_farm.json()["district"] == "Musanze"

    field = client.post(
        f"/api/v1/farms/{farm['id']}/fields",
        headers=auth,
        json={"name": "North plot", "crop_note": "Maize", "side_a": 20, "side_b": 10, "side_c": 20, "side_d": 10, "side_unit": "m"},
    ).json()
    updated_field = client.put(
        f"/api/v1/farms/{farm['id']}/fields/{field['id']}",
        headers=auth,
        json={"name": "Kitchen plot", "crop_note": "Beans", "side_a": 30, "side_b": 10, "side_c": 30, "side_d": 10, "side_unit": "m"},
    )
    assert updated_field.status_code == 200
    assert updated_field.json()["name"] == "Kitchen plot"
    assert updated_field.json()["crop_note"] == "Beans"
    assert updated_field.json()["area_m2"] == 300


def test_four_side_unit_conversion_and_area(client, auth):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    response = client.post(f"/api/v1/farms/{farm_id}/fields", headers=auth, json={"name": "North plot", "side_a": 10000, "side_b": 5000, "side_c": 10000, "side_d": 5000, "side_unit": "cm"})
    assert response.status_code == 201
    assert response.json()["area_m2"] == 5000
    assert response.json()["area_source"] == "manual_estimate"


def test_crop_plan_reuses_field_area_and_reports_honest_nisr_baseline(client, auth):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    field = client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=auth,
        json={"name": "Potato plot", "crop_note": "Irish potato", "side_a": 100, "side_b": 50, "side_c": 100, "side_d": 50, "side_unit": "m"},
    ).json()
    response = client.post(
        "/api/v1/crop-planning/plans",
        headers=auth,
        json={
            "field_id": field["id"],
            "crop": "Irish potato",
            "season": "B",
            "planned_planting_date": "2027-03-15",
            "irrigation": "rainfed",
            "previous_crop": "Beans",
        },
    )
    assert response.status_code == 201
    result = response.json()
    assert result["context"]["district"] == "Musanze"
    assert result["context"]["area_ha"] == 0.5
    assert result["prediction"]["yield_range_t_ha"] == [6.7, 6.8]
    assert result["prediction"]["estimated_total_harvest_t"] == [3.35, 3.4]
    assert result["model"]["mae_t_ha"] is not None
    assert result["model"]["rmse_t_ha"] is not None
    assert result["model"]["ml_status"] == "not_trained"
    assert result["data_availability"]["broader_baseline_used"] is True
    assert len(result["sources"]) >= 2
    saved = client.get("/api/v1/crop-planning/plans", headers=auth).json()
    assert saved[0]["result"]["plan_id"] == result["plan_id"]


def test_crop_plan_uses_exact_district_observation_when_available(client, auth):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    field_id = client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=auth,
        json={"name": "Season C plot", "side_a": 100, "side_b": 50, "side_c": 100, "side_d": 50, "side_unit": "m"},
    ).json()["id"]
    response = client.post(
        "/api/v1/crop-planning/plans",
        headers=auth,
        json={
            "field_id": field_id,
            "crop": "Irish potato",
            "season": "C",
            "planned_planting_date": "2027-07-10",
            "irrigation": "available",
        },
    )
    assert response.status_code == 201
    result = response.json()
    assert result["data_availability"]["district_observations"] == 1
    assert result["data_availability"]["geography_used"] == "district anchor plus Rwanda baseline"
    assert result["prediction"]["yield_range_t_ha"][1] == 9.449


def test_crop_recommendations_use_field_history_and_verified_evidence(client, auth):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    field_id = client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=auth,
        json={"name": "Rotation plot", "crop_note": "Irish potato", "side_a": 100, "side_b": 50, "side_c": 100, "side_d": 50, "side_unit": "m"},
    ).json()["id"]
    saved = client.post(
        "/api/v1/crop-planning/plans",
        headers=auth,
        json={"field_id": field_id, "crop": "Irish potato", "season": "B", "planned_planting_date": "2027-03-10", "irrigation": "rainfed"},
    )
    assert saved.status_code == 201

    response = client.post(
        "/api/v1/crop-planning/recommendations",
        headers=auth,
        json={"field_id": field_id, "season": "B", "planned_planting_date": "2028-03-12"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["field"]["area_ha"] == 0.5
    assert result["last_recorded_crop"] == "Irish potato"
    assert result["crop_history"][0]["crop"] == "Irish potato"
    assert len(result["recommendations"]) == 3
    assert result["recommendations"][0]["national_observations"] >= 2
    assert result["recommendations"][0]["estimated_total_harvest_t"][0] >= 0
    assert "not a guarantee" in result["important_note"]
    assert result["rotation_reference"]["url"].startswith("https://www.fao.org/")


def test_irrigation_device_auth_decision_and_safe_command_flow(client, auth, monkeypatch):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    field_id = client.post(
        f"/api/v1/farms/{farm_id}/fields", headers=auth,
        json={"name": "Irrigated plot", "crop_note": "Maize", "side_a": 20, "side_b": 10, "side_c": 20, "side_d": 10, "side_unit": "m"},
    ).json()["id"]
    device = client.post("/api/v1/devices", headers=auth, json={
        "field_id": field_id, "name": "Pump controller", "device_uid": "FIELD-001", "port": "COM7",
        "sensors": [
            {"key": "soil_moisture", "name": "Soil moisture", "type": "soil_moisture", "unit": "%"},
            {"key": "tank_level", "name": "Tank level", "type": "water_level", "unit": "%"},
            {"key": "temperature", "name": "Temperature", "type": "temperature", "unit": "°C"},
            {"key": "flow_rate", "name": "Water flow", "type": "flow", "unit": "L/min"},
            {"key": "rainfall", "name": "Recent rainfall", "type": "rainfall", "unit": "mm"},
            {"key": "pump_relay", "name": "Pump relay", "type": "relay", "unit": None},
        ],
    }).json()
    credentials = client.post(f"/api/v1/iot/devices/{device['id']}/credentials", headers=auth).json()
    device_headers = {"X-Device-ID": credentials["device_uid"], "X-Device-Key": credentials["device_key"]}
    with SessionLocal.begin() as db:
        stored = db.get(Device, device["id"])
        stored.status = "connected"
        stored.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    assert client.get(f"/api/v1/devices/{device['id']}", headers=auth).json()["is_online"] is False
    heartbeat = client.post(
        "/api/v1/iot/heartbeat",
        headers=device_headers,
        json={"firmware_version": "heartbeat-test-1", "wifi_rssi": -55, "ip_address": "192.168.1.42"},
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "online"
    heartbeat_device = client.get(f"/api/v1/devices/{device['id']}", headers=auth).json()
    assert heartbeat_device["is_online"] is True
    assert heartbeat_device["firmware_version"] == "heartbeat-test-1"
    assert client.post("/api/v1/iot/readings", json={"readings": [{"key": "soil_moisture", "value": 20}] }).status_code == 422
    reading = client.post("/api/v1/iot/readings", headers=device_headers, json={"firmware_version": "test-1", "readings": [
        {"key": "soil_moisture", "value": 20, "unit": "%"},
        {"key": "tank_level", "value": 80, "unit": "%"},
        {"key": "temperature", "value": 24, "unit": "°C"},
        {"key": "flow_rate", "value": 6.5, "unit": "L/min"},
        {"key": "rainfall", "value": 0, "unit": "mm"},
    ]})
    assert reading.status_code == 200
    assert reading.json()["accepted"] == 5

    monkeypatch.setattr("app.services.irrigation.weather_dashboard", lambda *args, **kwargs: {
        "hourly": {"precipitation": [0] * 24, "precipitation_probability": [10] * 24},
        "current": {"temperature_2m": 24}, "provider": "Test weather", "generated_at": "2026-10-22T00:00:00Z",
    })
    status_response = client.get(f"/api/v1/irrigation/status?field_id={field_id}", headers=auth)
    assert status_response.status_code == 200
    assert status_response.json()["decision"] == "recommended"
    assert "below" in status_response.json()["reasons"][0]
    assert status_response.json()["measurements"]["flow_rate"]["value"] == 6.5

    client.patch(f"/api/v1/iot/devices/{device['id']}/remote-control?enabled=true", headers=auth)
    configured = client.put(f"/api/v1/irrigation/config?field_id={field_id}", headers=auth, json={
        "mode": "advisory", "safety_validated": True, "remote_control_enabled": True,
        "emergency_stop": False, "max_pump_runtime_seconds": 300, "cooldown_minutes": 15,
        "min_tank_percent": 15, "max_reading_age_minutes": 30, "moisture_trigger_percent": 32,
    })
    assert configured.status_code == 200
    device_config = client.get("/api/v1/iot/config", headers=device_headers)
    assert device_config.status_code == 200
    assert device_config.json()["fail_safe"] == "pump_off"
    assert device_config.json()["max_pump_runtime_seconds"] == 300
    assert client.post("/api/v1/iot/readings", headers=device_headers, json={"readings": [{"key": "rainfall", "value": 4, "unit": "mm"}]}).status_code == 200
    after_rain = client.get(f"/api/v1/irrigation/status?field_id={field_id}", headers=auth).json()
    assert after_rain["decision"] == "postpone"
    assert "recent" in after_rain["title"].lower()
    command = client.post("/api/v1/irrigation/commands", headers=auth, json={"field_id": field_id, "command": "start", "duration_seconds": 120})
    assert command.status_code == 201
    assert any("Manual override" in reason for reason in command.json()["reasons"])
    pending = client.get("/api/v1/iot/commands", headers=device_headers).json()
    assert pending[0]["command"] == "start"
    executed = client.post(f"/api/v1/iot/commands/{pending[0]['id']}/status", headers=device_headers, json={"status": "executed", "message": "Pump ON"})
    assert executed.status_code == 200
    assert executed.json()["status"] == "executed"
    completed = client.post(f"/api/v1/iot/commands/{pending[0]['id']}/status", headers=device_headers, json={"status": "completed", "message": "Runtime complete; pump OFF"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert client.post(f"/api/v1/iot/commands/{pending[0]['id']}/status", headers=device_headers, json={"status": "completed"}).status_code == 409
    with SessionLocal.begin() as db:
        stored = db.get(IrrigationCommand, pending[0]["id"])
        stored.status = "pending"
        stored.issued_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        stored.executed_at = None
    assert client.get("/api/v1/iot/commands", headers=device_headers).json() == []
    with SessionLocal() as db:
        assert db.get(IrrigationCommand, pending[0]["id"]).status == "rejected"


def test_irrigation_blocks_empty_tank_and_unvalidated_automatic_mode(client, auth, monkeypatch):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    field_id = client.post(f"/api/v1/farms/{farm_id}/fields", headers=auth, json={"name": "Dry tank plot", "side_a": 10, "side_b": 10, "side_c": 10, "side_d": 10, "side_unit": "m"}).json()["id"]
    device = client.post("/api/v1/devices", headers=auth, json={"field_id": field_id, "name": "Safety device", "device_uid": "FIELD-002", "port": "COM8", "sensors": [
        {"key": "soil_moisture", "name": "Soil", "type": "soil_moisture", "unit": "%"},
        {"key": "tank_level", "name": "Tank", "type": "water_level", "unit": "%"},
        {"key": "pump_relay", "name": "Relay", "type": "relay"},
    ]}).json()
    credentials = client.post(f"/api/v1/iot/devices/{device['id']}/credentials", headers=auth).json()
    device_headers = {"X-Device-ID": credentials["device_uid"], "X-Device-Key": credentials["device_key"]}
    client.post("/api/v1/iot/readings", headers=device_headers, json={"readings": [{"key": "soil_moisture", "value": 10, "unit": "%"}, {"key": "tank_level", "value": 4, "unit": "%"}]})
    monkeypatch.setattr("app.services.irrigation.weather_dashboard", lambda *args, **kwargs: {"hourly": {"precipitation": [0] * 24, "precipitation_probability": [0] * 24}, "current": {}, "provider": "Test", "generated_at": "now"})
    result = client.get(f"/api/v1/irrigation/status?field_id={field_id}", headers=auth).json()
    assert result["decision"] == "blocked"
    assert "tank" in result["title"].lower()
    auto = client.put(f"/api/v1/irrigation/config?field_id={field_id}", headers=auth, json={"mode": "automatic", "safety_validated": False})
    assert auto.status_code == 422


def test_plant_lens_stores_photo_without_inventing_prediction_when_model_missing(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.plant_lens._validate_photo_quality", lambda _path: {"width": 300, "height": 300})
    monkeypatch.setattr("app.services.plant_lens._predict_with_fastai", lambda *_args: (_ for _ in ()).throw(RuntimeError("No trained Plant Lens model is installed")))
    image = b"\xff\xd8\xff" + b"photo" * 200
    response = client.post(
        "/api/v1/plant-lens/analyze", headers=auth,
        data={"crop_id": "irish-potato"}, files={"image": ("leaf.jpg", image, "image/jpeg")},
    )
    assert response.status_code == 201
    result = response.json()
    assert result["prediction"]["analysis_status"] == "model_unavailable"
    assert result["prediction"]["confidence"] is None
    assert result["review_status"] == "awaiting_model"
    cases = client.get("/api/v1/plant-lens/cases", headers=auth).json()
    assert cases[0]["id"] == result["id"]
    stored_image = client.get(f"/api/v1/plant-lens/cases/{result['id']}/image", headers=auth)
    assert stored_image.status_code == 200
    assert stored_image.content == image


def test_plant_lens_fastai_result_is_probabilistic_and_requires_expert_review(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.plant_lens._validate_photo_quality", lambda _path: {"width": 300, "height": 300})
    monkeypatch.setattr("app.services.plant_lens._predict_with_fastai", lambda *_args: [
        {"label": "late blight", "confidence": 0.82},
        {"label": "early blight", "confidence": 0.13},
        {"label": "healthy", "confidence": 0.05},
    ])
    image = b"\x89PNG\r\n\x1a\n" + b"plant" * 200
    response = client.post(
        "/api/v1/plant-lens/analyze", headers=auth,
        data={"crop_id": "irish-potato"}, files={"image": ("potato.png", image, "image/png")},
    )
    assert response.status_code == 201
    prediction = response.json()["prediction"]
    assert prediction["classification"] == "late blight"
    assert prediction["confidence"] == 0.82
    assert prediction["alternatives"][0]["label"] == "early blight"
    assert prediction["expert_confirmation_required"] is True
    assert "not a definitive diagnosis" in prediction["disclaimer"]


def test_plant_lens_rejects_unsupported_image_instead_of_forcing_disease(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.plant_lens._validate_photo_quality", lambda _path: {"width": 300, "height": 300})
    monkeypatch.setattr("app.services.plant_lens._predict_with_fastai", lambda *_args: [
        {"label": "unsupported", "confidence": 0.91},
        {"label": "healthy", "confidence": 0.05},
        {"label": "late blight", "confidence": 0.04},
    ])
    image = b"\x89PNG\r\n\x1a\n" + b"not-potato" * 100
    response = client.post(
        "/api/v1/plant-lens/analyze", headers=auth,
        data={"crop_id": "irish-potato"}, files={"image": ("other.png", image, "image/png")},
    )
    assert response.status_code == 201
    result = response.json()
    assert result["prediction"]["analysis_status"] == "unsupported_image"
    assert result["prediction"]["classification"] == "unsupported"
    assert result["review_status"] == "rejected_unsupported"
    assert "forcing" in result["prediction"]["disclaimer"]


def test_plant_lens_reports_uncertainty_when_classes_are_too_close(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.plant_lens._validate_photo_quality", lambda _path: {"width": 300, "height": 300})
    monkeypatch.setattr("app.services.plant_lens._predict_with_fastai", lambda *_args: [
        {"label": "late blight", "confidence": 0.48},
        {"label": "early blight", "confidence": 0.41},
        {"label": "healthy", "confidence": 0.11},
    ])
    image = b"\xff\xd8\xff" + b"uncertain" * 100
    response = client.post(
        "/api/v1/plant-lens/analyze", headers=auth,
        data={"crop_id": "irish-potato"}, files={"image": ("uncertain.jpg", image, "image/jpeg")},
    )
    assert response.status_code == 201
    result = response.json()
    assert result["prediction"]["analysis_status"] == "uncertain"
    assert result["prediction"]["classification"] is None
    assert result["review_status"] == "needs_better_photo"


def test_plant_lens_supports_tomato_with_crop_specific_result(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.plant_lens._validate_photo_quality", lambda _path: {"width": 300, "height": 300})
    monkeypatch.setattr("app.services.plant_lens._predict_with_fastai", lambda _path, crop_id: [
        {"label": "tomato mosaic virus", "confidence": 0.98},
        {"label": "tomato yellow leaf curl virus", "confidence": 0.01},
        {"label": "healthy", "confidence": 0.01},
    ])
    image = b"\xff\xd8\xff" + b"tomato" * 100
    response = client.post(
        "/api/v1/plant-lens/analyze", headers=auth,
        data={"crop_id": "tomato"}, files={"image": ("tomato.jpg", image, "image/jpeg")},
    )
    assert response.status_code == 201
    result = response.json()
    assert result["crop_id"] == "tomato"
    assert result["crop_name"] == "Tomato"
    assert result["prediction"]["classification"] == "tomato mosaic virus"
    assert "mosaic" in result["prediction"]["possible_condition"].lower()
    assert result["prediction"]["expert_confirmation_required"] is True


def test_plant_lens_refuses_borderline_tomato_prediction(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.plant_lens._validate_photo_quality", lambda _path: {"width": 300, "height": 300})
    monkeypatch.setattr("app.services.plant_lens._predict_with_fastai", lambda _path, crop_id: [
        {"label": "tomato mosaic virus", "confidence": 0.88},
        {"label": "tomato yellow leaf curl virus", "confidence": 0.07},
        {"label": "healthy", "confidence": 0.05},
    ])
    image = b"\xff\xd8\xff" + b"tomato-borderline" * 100
    response = client.post(
        "/api/v1/plant-lens/analyze", headers=auth,
        data={"crop_id": "tomato"}, files={"image": ("tomato.jpg", image, "image/jpeg")},
    )
    assert response.status_code == 201
    prediction = response.json()["prediction"]
    assert prediction["analysis_status"] == "uncertain"
    assert prediction["classification"] is None
    assert prediction["field_validation"] == "not_completed_for_rwanda"
    assert "safer" in prediction["disclaimer"].lower()


def test_plant_lens_groups_overlapping_tomato_spots(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.plant_lens._validate_photo_quality", lambda _path: {"width": 300, "height": 300})
    monkeypatch.setattr("app.services.plant_lens._predict_with_fastai", lambda _path, crop_id: [
        {"label": "bacterial spot", "confidence": 0.55},
        {"label": "early blight", "confidence": 0.38},
        {"label": "leaf mold", "confidence": 0.04},
        {"label": "healthy", "confidence": 0.03},
    ])
    image = b"\xff\xd8\xff" + b"tomato-spots" * 100
    response = client.post(
        "/api/v1/plant-lens/analyze", headers=auth,
        data={"crop_id": "tomato"}, files={"image": ("spots.jpg", image, "image/jpeg")},
    )
    assert response.status_code == 201
    prediction = response.json()["prediction"]
    assert prediction["analysis_status"] == "completed"
    assert prediction["classification"] == "tomato leaf spot pattern"
    assert prediction["confidence"] == 0.93
    assert prediction["model_top_class"] == "bacterial spot"
    assert prediction["leading_candidate"] == "bacterial spot"
    assert prediction["leading_candidate_score"] == 0.55
    assert prediction["candidate_is_confirmed"] is False


def test_plant_lens_gemini_advice_is_grounded_safe_and_cached(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.plant_lens._validate_photo_quality", lambda _path: {"width": 300, "height": 300})
    monkeypatch.setattr("app.services.plant_lens._predict_with_fastai", lambda _path, crop_id: [
        {"label": "late blight", "confidence": 0.99},
        {"label": "unsupported", "confidence": 0.005},
        {"label": "healthy", "confidence": 0.005},
    ])
    monkeypatch.setattr("app.services.plant_lens.settings.gemini_api_key", "test-gemini-key")
    calls = []

    class GeminiResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [{
                    "content": {"parts": [{"text": "Do now\nRemove badly affected leaves.\n\nCheck next\nInspect nearby plants.\n\nTreatment or medicine\nConfirm the diagnosis before selecting a registered product.\n\nGet expert help\nContact a qualified agronomist."}]},
                    "groundingMetadata": {"groundingChunks": [{"web": {"title": "RAB crop protection guidance", "uri": "https://www.rab.gov.rw/crop-protection"}}]},
                }]
            }

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return GeminiResponse()

    monkeypatch.setattr("app.services.plant_lens.httpx.post", fake_post)
    image = b"\xff\xd8\xff" + b"tomato-late-blight" * 100
    created = client.post(
        "/api/v1/plant-lens/analyze", headers=auth,
        data={"crop_id": "tomato"}, files={"image": ("tomato.jpg", image, "image/jpeg")},
    ).json()
    first = client.post(f"/api/v1/plant-lens/cases/{created['id']}/advice", headers=auth)
    assert first.status_code == 200
    advice = first.json()
    assert advice["status"] == "ready"
    assert advice["response_mode"] == "gemini_grounded_web"
    assert advice["sources"][0]["source_url"].startswith("https://www.rab.gov.rw")
    assert "image result alone" in advice["safety_notice"]
    assert calls[0]["json"]["tools"] == [{"google_search": {}}]
    system_text = calls[0]["json"]["systemInstruction"]["parts"][0]["text"]
    assert "Do not provide pesticide dose" in system_text

    cached = client.post(f"/api/v1/plant-lens/cases/{created['id']}/advice", headers=auth)
    assert cached.status_code == 200
    assert cached.json()["generated_at"] == advice["generated_at"]
    assert len(calls) == 1


def test_map_polygon_is_authoritative(client, auth):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    polygon = {"type": "Polygon", "coordinates": [[[29.63, -1.50], [29.631, -1.50], [29.631, -1.499], [29.63, -1.50]]]}
    response = client.post(f"/api/v1/farms/{farm_id}/fields", headers=auth, json={"name": "Mapped plot", "boundary_geojson": polygon})
    assert response.status_code == 201
    assert response.json()["area_m2"] > 0
    assert response.json()["area_source"] == "map"


def test_location_search_is_rwanda_limited_and_cached(client, auth, monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"display_name": "Musanze, Northern Province, Rwanda", "lat": "-1.4998", "lon": "29.6349", "address": {"city": "Musanze", "state": "Northern Province", "country_code": "rw"}}]

    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)
    first = client.get("/api/v1/locations/search?q=Musanze", headers=auth)
    second = client.get("/api/v1/locations/search?q=Musanze", headers=auth)
    assert first.status_code == 200
    assert first.json()[0]["district"] == "Musanze"
    assert first.json()[0]["provider"] == "OpenStreetMap Nominatim"
    assert len(calls) == 1
    assert calls[0][1]["params"]["countrycodes"] == "rw"
    assert second.json() == first.json()


def test_cascading_official_location_endpoints(client, auth):
    assert client.get("/api/v1/locations/provinces", headers=auth).json() == [{"code": 4, "name": "NORTH"}]
    assert client.get("/api/v1/locations/districts?province_code=4", headers=auth).json()[0]["name"] == "Musanze"
    assert client.get("/api/v1/locations/sectors?district_code=403", headers=auth).json()[0]["code"] == "040310"
    assert client.get("/api/v1/locations/cells?sector_code=040310", headers=auth).json()[0]["name"] == "Ruhengeri"
    assert client.get("/api/v1/locations/villages?cell_code=4031001", headers=auth).json()[0]["name"] == "User confirmed"


def test_rejects_mismatched_location_hierarchy(client, auth):
    payload = farm_payload()
    payload["village_code"] = 999999999
    assert client.post("/api/v1/farms", headers=auth, json=payload).status_code == 422


def test_cell_map_focus_uses_full_hierarchy_and_returns_boundary(client, auth, monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"lat": "-1.5", "lon": "29.63", "boundingbox": ["-1.51", "-1.49", "29.62", "29.64"], "geojson": {"type": "Polygon", "coordinates": [[[29.62, -1.51], [29.64, -1.51], [29.64, -1.49], [29.62, -1.51]]]}}]

    captured = {}

    def fake_get(url, **kwargs):
        captured.update(kwargs["params"])
        return Response()

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)
    response = client.get("/api/v1/locations/cells/4031001/map-focus", headers=auth)
    assert response.status_code == 200
    assert response.json()["navigation_only"] is True
    assert response.json()["exact_cell_match"] is True
    assert response.json()["focus_level"] == "cell"
    assert response.json()["geometry"]["type"] == "Polygon"
    assert captured["q"] == "Ruhengeri, Muhoza, Musanze, Rwanda"
    assert captured["polygon_geojson"] == 1


def test_cell_map_focus_falls_back_to_sector_boundary(client, auth, monkeypatch):
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    queries = []

    def fake_get(url, **kwargs):
        queries.append(kwargs["params"]["q"])
        if len(queries) == 1:
            return Response([])
        return Response([{"lat": "-1.48", "lon": "29.60", "boundingbox": ["-1.55", "-1.42", "29.52", "29.68"], "geojson": {"type": "Polygon", "coordinates": [[[29.52, -1.55], [29.68, -1.55], [29.68, -1.42], [29.52, -1.55]]]}}])

    monkeypatch.setattr("app.services.geocoding.httpx.get", fake_get)
    response = client.get("/api/v1/locations/cells/4031001/map-focus", headers=auth)
    assert response.status_code == 200
    assert response.json()["focus_level"] == "sector"
    assert response.json()["exact_cell_match"] is False
    assert queries == ["Ruhengeri, Muhoza, Musanze, Rwanda", "Muhoza, Musanze, Rwanda"]


def test_weather_dashboard_uses_farm_coordinates_and_sqlite_cache(client, auth, monkeypatch):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    calls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, **kwargs):
        calls.append((url, kwargs["params"]))
        if "archive" in url:
            return Response({"daily": {"time": ["2026-09-01", "2026-09-02"], "temperature_2m_max": [24, 26], "temperature_2m_min": [14, 16], "precipitation_sum": [2, 3]}})
        return Response({
            "timezone": "Africa/Kigali",
            "current": {"time": "2026-10-22T12:00", "temperature_2m": 23, "relative_humidity_2m": 71, "precipitation": 0, "rain": 0, "weather_code": 2, "wind_speed_10m": 8},
            "hourly": {"time": ["2026-10-22T12:00"], "temperature_2m": [23], "relative_humidity_2m": [71], "precipitation_probability": [65], "precipitation": [1.2], "rain": [1.2], "weather_code": [61], "wind_speed_10m": [8]},
            "daily": {"time": ["2026-10-22"], "weather_code": [61], "temperature_2m_max": [25], "temperature_2m_min": [15], "precipitation_sum": [4], "rain_sum": [4], "precipitation_probability_max": [70], "wind_speed_10m_max": [14]},
        })

    monkeypatch.setattr("app.services.weather.httpx.get", fake_get)
    first = client.get(f"/api/v1/weather?farm_id={farm_id}", headers=auth)
    second = client.get(f"/api/v1/weather?farm_id={farm_id}", headers=auth)
    assert first.status_code == 200
    assert first.json()["location"]["source"] == "farm coordinates"
    assert first.json()["historical_months"][0]["rainfall_mm"] == 5
    assert "soil-moisture sensor" in first.json()["recommendations"][0]["uncertainty"]
    assert first.json()["warnings_supported"] is False
    assert second.json()["cache"]["hit"] is True
    assert len(calls) == 2
    assert calls[0][1]["forecast_days"] == 7


def test_esp32_device_is_assigned_to_field_and_persists_real_reading(client, auth, monkeypatch):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    field_id = client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=auth,
        json={"name": "Sensor plot", "side_a": 20, "side_b": 10, "side_c": 20, "side_d": 10, "side_unit": "m"},
    ).json()["id"]
    payload = {
        "field_id": field_id,
        "name": "North ESP32",
        "device_uid": "esp32-test-001",
        "port": "COM99",
        "board": "ESP32 DevKit",
        "firmware_version": "1.0.0",
        "sensors": [{"key": "soil", "name": "Soil moisture", "type": "soil_moisture", "unit": "%", "pin": "GPIO34"}],
    }
    created = client.post("/api/v1/devices", headers=auth, json=payload)
    assert created.status_code == 201
    assert created.json()["field_id"] == field_id
    assert created.json()["sensors"][0]["latest_value"] is None
    assert created.json()["status"] == "online"
    assert created.json()["is_online"] is True

    monkeypatch.setattr("app.api.exchange", lambda *args: {"protocol": "agrinox-1", "readings": {"soil": 47.5}})
    reading = client.post(f"/api/v1/devices/{created.json()['id']}/read", headers=auth)
    assert reading.status_code == 200
    assert reading.json()["sensors"][0]["latest_value"] == 47.5
    assert reading.json()["field_name"] == "Sensor plot"

    edited = client.patch(
        f"/api/v1/devices/{created.json()['id']}",
        headers=auth,
        json={"name": "Renamed ESP32", "field_id": None},
    )
    assert edited.status_code == 200
    assert edited.json()["name"] == "Renamed ESP32"
    assert edited.json()["field_id"] is None
    assert edited.json()["field_name"] is None

    detail = client.get(f"/api/v1/devices/{created.json()['id']}", headers=auth)
    assert detail.status_code == 200
    assert detail.json()["sensors"][0]["latest_value"] == 47.5

    with SessionLocal.begin() as db:
        stored = db.get(Device, created.json()["id"])
        stored.status = "connected"
        stored.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale = client.get(f"/api/v1/devices/{created.json()['id']}", headers=auth)
    assert stale.status_code == 200
    assert stale.json()["status"] == "offline"
    assert stale.json()["is_online"] is False
    assert stale.json()["last_seen_seconds_ago"] >= 600


def test_soil_dashboard_combines_context_measurements_and_safe_advice(client, auth):
    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    field_id = client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=auth,
        json={"name": "Soil plot", "side_a": 20, "side_b": 10, "side_c": 20, "side_d": 10, "side_unit": "m"},
    ).json()["id"]
    context = client.put(
        f"/api/v1/soil/fields/{field_id}/context",
        headers=auth,
        json={"crop_type": "Maize", "growth_stage": "Vegetative"},
    )
    assert context.status_code == 200

    created = client.post(
        f"/api/v1/soil/fields/{field_id}/readings",
        headers=auth,
        json={
            "source": "manual",
            "note": "Low-cost field meter",
            "measurements": [
                {"measurement_type": "nitrogen", "value": 18, "unit": "mg/kg", "calibration_status": "uncalibrated", "reliability": "needs_review"},
                {"measurement_type": "moisture", "value": 16, "unit": "%", "calibration_status": "calibrated", "reliability": "reliable"},
            ],
        },
    )
    assert created.status_code == 201
    dashboard = client.get(f"/api/v1/soil/fields/{field_id}", headers=auth)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["context"]["crop_type"] == "Maize"
    assert body["summary"]["available"] == 2
    assert next(item for item in body["measurements"] if item["type"] == "moisture")["latest"]["value"] == 16
    nitrogen_advice = next(item for item in body["advisories"] if "Nitrogen" in item["title"])
    moisture_advice = next(item for item in body["advisories"] if "moisture" in item["title"])
    assert "cannot support a fertilizer decision" in nitrogen_advice["message"]
    assert "irrigate only if" in moisture_advice["action"]
    assert body["data_quality"]["status"] in ("low", "medium", "high")
    assert body["summary"]["current"] == 2
    assert next(item for item in body["measurements"] if item["type"] == "moisture")["latest"]["quality_status"] == "reliable"
    assert "does not replace" in body["safety_note"]

    rice_context = client.put(
        f"/api/v1/soil/fields/{field_id}/context",
        headers=auth,
        json={"crop_type": "Rice", "growth_stage": "Flowering"},
    )
    assert rice_context.status_code == 200
    rice_dashboard = client.get(f"/api/v1/soil/fields/{field_id}", headers=auth).json()
    rice_stage_advice = next(item for item in rice_dashboard["advisories"] if "Rice · Flowering" in item["title"])
    rice_moisture_advice = next(item for item in rice_dashboard["advisories"] if "moisture" in item["title"])
    assert "highly sensitive to water stress" in rice_stage_advice["message"]
    assert "rice field" in rice_moisture_advice["action"]

    potato_context = client.put(
        f"/api/v1/soil/fields/{field_id}/context",
        headers=auth,
        json={"crop_type": "Irish potatoes", "growth_stage": "Maturity"},
    )
    assert potato_context.status_code == 200
    potato_dashboard = client.get(f"/api/v1/soil/fields/{field_id}", headers=auth).json()
    potato_stage_advice = next(item for item in potato_dashboard["advisories"] if "Irish potatoes · Maturity" in item["title"])
    assert "need less water" in potato_stage_advice["message"]
    assert "Reduce irrigation" in potato_stage_advice["action"]

    lab_result = client.post(
        f"/api/v1/soil/fields/{field_id}/readings",
        headers=auth,
        json={
            "source": "laboratory",
            "measurements": [{"measurement_type": "ph", "value": 6.0, "unit": "pH"}],
        },
    )
    assert lab_result.status_code == 201
    potato_with_ph = client.get(f"/api/v1/soil/fields/{field_id}", headers=auth).json()
    ph_advice = next(item for item in potato_with_ph["advisories"] if item["title"] == "According to Soil pH")
    assert "above the FAO reference range" in ph_advice["message"]
    assert "5–5.4" in ph_advice["message"]

    invalid_future = client.post(
        f"/api/v1/soil/fields/{field_id}/readings",
        headers=auth,
        json={
            "source": "manual",
            "measured_at": "2099-01-01T00:00:00Z",
            "measurements": [{"measurement_type": "nitrogen", "value": -1, "unit": "mg/kg"}],
        },
    )
    assert invalid_future.status_code == 422


def test_knowledge_library_search_grounded_chat_and_conversation_storage(client, auth, monkeypatch):
    overview = client.get("/api/v1/knowledge/overview", headers=auth)
    assert overview.status_code == 200
    assert overview.json()["article_count"] == 11
    assert overview.json()["verified_count"] == 11
    assert overview.json()["ai_available"] is False

    search = client.get("/api/v1/knowledge/articles?q=Tubura&language=rw", headers=auth)
    assert search.status_code == 200
    assert len(search.json()) == 1
    assert "Tubura" in search.json()[0]["title"]
    assert search.json()[0]["sources"][0]["url"].startswith("https://")

    article = client.get(f"/api/v1/knowledge/articles/{search.json()[0]['slug']}?language=en", headers=auth)
    assert article.status_code == 200
    assert article.json()["review_status"] == "source_verified"
    assert article.json()["content_en"]
    assert article.json()["content_rw"]

    asked = client.post(
        "/api/v1/knowledge/ask",
        headers=auth,
        json={"question": "What does Tubura mean?", "language": "en"},
    )
    assert asked.status_code == 200
    answer = asked.json()
    assert answer["response_mode"] == "verified_retrieval"
    assert "grow exponentially" in answer["answer"]
    assert len(answer["answer"]) < 400
    assert answer["answer"].endswith("[1]")
    assert answer["citations"]
    assert len(answer["citations"]) == 1

    irrigation = client.post(
        "/api/v1/knowledge/ask",
        headers=auth,
        json={"question": "How should I decide when to irrigate?", "language": "en"},
    )
    assert irrigation.status_code == 200
    assert "crop stage" in irrigation.json()["answer"]
    assert "rainfall forecast alone" in irrigation.json()["answer"]
    assert len(irrigation.json()["answer"]) < 500
    assert irrigation.json()["citations"][0]["article_title"] == "Irrigation practices and field decisions"

    conversation = client.get(f"/api/v1/knowledge/conversations/{answer['conversation_id']}", headers=auth)
    assert conversation.status_code == 200
    assert [message["role"] for message in conversation.json()["messages"]] == ["user", "assistant"]
    assert conversation.json()["messages"][1]["citations"][0]["source_url"].startswith("https://")

    unavailable = client.post(
        "/api/v1/knowledge/ask",
        headers=auth,
        json={"question": "What is the policy for farming on Mars?", "language": "en"},
    )
    assert unavailable.status_code == 200
    assert "do not have enough verified information" in unavailable.json()["answer"]
    assert unavailable.json()["citations"] == []

    monkeypatch.setattr(
        "app.services.knowledge._gemini_answer",
        lambda question, language, retrieved, history: (
            "Use the locally verified guidance and confirm current details with RAB. [1]",
            [{
                "article_id": None,
                "article_title": "RAB current guidance",
                "source_url": "https://www.rab.gov.rw/",
                "score": 1.0,
            }],
            "gemini-3.8-flash",
            "gemini_grounded_web",
        ),
    )
    ai_answer = client.post(
        "/api/v1/knowledge/ask",
        headers=auth,
        json={"question": "Give current Rwanda agricultural guidance", "language": "en"},
    )
    assert ai_answer.status_code == 200
    assert ai_answer.json()["response_mode"] == "gemini_grounded_web"
    assert any(item["source_url"] == "https://www.rab.gov.rw/" for item in ai_answer.json()["citations"])


def test_casual_greeting_uses_conversation_response(client, auth, monkeypatch):
    monkeypatch.setattr(
        "app.services.knowledge._gemini_answer",
        lambda question, language, retrieved, history: (
            "Hello! How can I help with your farming today?",
            [],
            "gemini-3.6-flash",
            "gemini_conversation",
        ),
    )
    response = client.post(
        "/api/v1/knowledge/ask",
        headers=auth,
        json={"question": "hello?", "language": "en"},
    )
    assert response.status_code == 200
    assert response.json()["response_mode"] == "gemini_conversation"
    assert response.json()["model_name"] == "gemini-3.6-flash"
    assert response.json()["citations"] == []


def test_misspelled_greeting_is_understood_without_verified_record(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.knowledge.settings.gemini_api_key", None)
    response = client.post(
        "/api/v1/knowledge/ask",
        headers=auth,
        json={"question": "hrllo", "language": "en"},
    )
    assert response.status_code == 200
    assert response.json()["response_mode"] == "conversation_fallback"
    assert response.json()["answer"].startswith("Hello!")
    assert response.json()["citations"] == []


def test_misspelled_kinyarwanda_farm_term_retrieves_verified_article(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.knowledge.settings.gemini_api_key", None)
    response = client.post(
        "/api/v1/knowledge/ask",
        headers=auth,
        json={"question": "igihebwe ni iki?", "language": "rw"},
    )
    assert response.status_code == 200
    assert response.json()["response_mode"] == "verified_retrieval"
    assert response.json()["citations"]
    assert response.json()["citations"][0]["article_title"] == "Ibihembwe by'ihinga A, B na C mu Rwanda"


def test_gemini_grounding_metadata_becomes_numbered_citations():
    from app.services.knowledge import _extract_gemini_result

    payload = {
        "candidates": [{
            "content": {"parts": [{"text": "Use locally verified agricultural guidance."}]},
            "groundingMetadata": {
                "groundingChunks": [{"web": {"uri": "https://example.test/source", "title": "Verified source"}}],
                "groundingSupports": [{
                    "segment": {"startIndex": 0, "endIndex": 43},
                    "groundingChunkIndices": [0],
                }],
            },
        }],
    }
    text, citations = _extract_gemini_result(payload, citation_offset=2)
    assert text.endswith("[3]")
    assert citations == [{
        "article_id": None,
        "article_title": "Verified source",
        "source_url": "https://example.test/source",
        "score": 1.0,
    }]


def test_gemini_internal_thought_text_is_not_shown_to_farmer():
    from app.services.knowledge import _extract_gemini_result

    payload = {
        "candidates": [{
            "content": {"parts": [
                {"text": "Check constraints and language", "thought": True},
                {"text": "Hello! How can I help with your farm today?"},
            ]},
        }],
    }
    text, citations = _extract_gemini_result(payload)
    assert text == "Hello! How can I help with your farm today?"
    assert citations == []


def test_dashboard_firmware_install_auto_names_and_registers_device(client, auth, monkeypatch):
    configured = {}
    monkeypatch.setattr("app.api.flash_firmware", lambda port: {
        "protocol": "agrinox-1",
        "device_uid": "esp32-aabbcc112233",
        "board": "ESP32 NPK monitor",
        "firmware": "agrinox-npk-1.0.0",
        "sensors": [
            {"key": "nitrogen", "name": "Soil nitrogen (N)", "type": "nitrogen", "unit": "mg/kg", "pin": "RS485 RX2/TX2"},
            {"key": "phosphorus", "name": "Soil phosphorus (P)", "type": "phosphorus", "unit": "mg/kg", "pin": "RS485 RX2/TX2"},
            {"key": "potassium", "name": "Soil potassium (K)", "type": "potassium", "unit": "mg/kg", "pin": "RS485 RX2/TX2"},
        ],
    })
    monkeypatch.setattr("app.api.local_device_api_url", lambda configured_url: "http://192.168.1.20:8000/api/v1")

    def capture_configuration(port, ssid, password, server_url, device_key):
        configured.update(port=port, ssid=ssid, password=password, server_url=server_url, device_key=device_key)
        return {"protocol": "agrinox-1", "configured": True}

    monkeypatch.setattr("app.api.configure_firmware", capture_configuration)
    response = client.post(
        "/api/v1/devices/firmware/install",
        headers=auth,
        json={"port": "COM6", "wifi_ssid": "Farm WiFi", "wifi_password": "safe-pass-123"},
    )
    assert response.status_code == 201
    result = response.json()
    assert result["device"]["name"] == "NPK Monitor 112233"
    assert result["device"]["field_id"] is None
    assert len(result["device"]["sensors"]) == 3
    assert result["field_assignment_required"] is True
    assert configured["password"] == "safe-pass-123"
    assert configured["server_url"] == "http://192.168.1.20:8000/api/v1"
    assert configured["device_key"]
    assert "safe-pass-123" not in response.text

    farm_id = client.post("/api/v1/farms", headers=auth, json=farm_payload()).json()["id"]
    field_id = client.post(
        f"/api/v1/farms/{farm_id}/fields",
        headers=auth,
        json={"name": "NPK plot", "side_a": 20, "side_b": 10, "side_c": 20, "side_d": 10, "side_unit": "m"},
    ).json()["id"]
    assigned = client.post("/api/v1/devices", headers=auth, json={
        "field_id": field_id,
        "name": "NPK Monitor 112233",
        "device_uid": "esp32-aabbcc112233",
        "port": "COM6",
        "firmware_version": "agrinox-npk-1.0.0",
        "sensors": [
            {"key": "nitrogen", "name": "Soil nitrogen (N)", "type": "nitrogen", "unit": "mg/kg"},
            {"key": "phosphorus", "name": "Soil phosphorus (P)", "type": "phosphorus", "unit": "mg/kg"},
            {"key": "potassium", "name": "Soil potassium (K)", "type": "potassium", "unit": "mg/kg"},
        ],
    })
    assert assigned.status_code == 201
    assert assigned.json()["id"] == result["device"]["id"]
    assert assigned.json()["field_id"] == field_id
    assert len(client.get("/api/v1/devices", headers=auth).json()) == 1

