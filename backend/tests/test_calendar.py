from datetime import datetime, timedelta, timezone


def create_field(client, auth):
    farm = client.post("/api/v1/farms", headers=auth, json={
        "name": "Calendar Farm", "province": "ignored", "district": "ignored", "sector": "ignored",
        "cell": "ignored", "village": "ignored", "province_code": 4, "district_code": 403,
        "sector_code": "040310", "cell_code": 4031001, "village_code": 403100101,
        "latitude": -1.499, "longitude": 29.634,
    }).json()
    return client.post(
        f"/api/v1/farms/{farm['id']}/fields", headers=auth,
        json={"name": "Potato field", "crop_note": "Irish potatoes", "side_a": 20, "side_b": 10, "side_c": 20, "side_d": 10, "side_unit": "m"},
    ).json()


def test_calendar_task_lifecycle_recurring_and_reminders(client, auth):
    field = create_field(client, auth)
    now = datetime.now(timezone.utc)
    created = client.post("/api/v1/calendar/tasks", headers=auth, json={
        "field_id": field["id"], "title": "Scout for symptoms", "category": "pest_scouting",
        "crop": "Irish potatoes", "growth_stage": "vegetative",
        "due_at": (now + timedelta(hours=2)).isoformat(), "reminder_at": (now - timedelta(minutes=5)).isoformat(),
        "recurrence": "weekly", "recurrence_interval": 1, "email_reminder": False,
    })
    assert created.status_code == 201
    task = created.json()
    assert task["farm_name"] == "Calendar Farm"
    assert task["field_name"] == "Potato field"

    reminders = client.get("/api/v1/calendar/reminders", headers=auth).json()
    assert [item["id"] for item in reminders] == [task["id"]]

    patched = client.patch(f"/api/v1/calendar/tasks/{task['id']}", headers=auth, json={"title": "Scout and record symptoms"})
    assert patched.status_code == 200
    assert patched.json()["title"] == "Scout and record symptoms"

    completed = client.post(f"/api/v1/calendar/tasks/{task['id']}/complete", headers=auth)
    assert completed.status_code == 200
    assert completed.json()["task"]["status"] == "completed"
    assert completed.json()["next_task"]["status"] == "pending"
    assert len(client.get("/api/v1/calendar/tasks", headers=auth).json()) == 2

    overview = client.get("/api/v1/calendar/overview", headers=auth).json()
    assert overview["total_tasks"] == 2
    assert overview["email_notifications"]["configured"] is False


def test_calendar_suggestions_are_scoped_and_transparent(client, auth):
    field = create_field(client, auth)
    result = client.post("/api/v1/calendar/suggestions", headers=auth, json={
        "field_id": field["id"], "crop": "Irish potatoes", "planting_date": "2026-10-01",
    })
    assert result.status_code == 200
    suggestions = result.json()
    assert {item["category"] for item in suggestions} >= {"soil_preparation", "planting", "pest_scouting", "harvesting"}
    assert all(item["source_url"].startswith("https://") for item in suggestions)
    assert all("confirm" in item["evidence_note"].lower() for item in suggestions)

    second_auth = client.post("/api/v1/auth/register", json={"email": "other@example.com", "full_name": "Other Farmer", "password": "securepass"}).json()["access_token"]
    forbidden = client.post("/api/v1/calendar/suggestions", headers={"Authorization": f"Bearer {second_auth}"}, json={
        "field_id": field["id"], "crop": "Maize", "planting_date": "2026-10-01",
    })
    assert forbidden.status_code == 404


def test_saved_crop_plan_links_to_calendar_once(client, auth):
    field = create_field(client, auth)
    plan_response = client.post("/api/v1/crop-planning/plans", headers=auth, json={
        "field_id": field["id"], "crop": "Irish potato", "season": "B",
        "planned_planting_date": "2026-03-10", "irrigation": "available",
    })
    assert plan_response.status_code == 201
    plan_id = plan_response.json()["plan_id"]

    linked = client.post(f"/api/v1/crop-planning/plans/{plan_id}/calendar", headers=auth)
    assert linked.status_code == 201
    assert linked.json()["created"] is True
    assert linked.json()["task_count"] >= 7
    assert all(item["crop_plan_id"] == plan_id for item in linked.json()["tasks"])

    repeated = client.post(f"/api/v1/crop-planning/plans/{plan_id}/calendar", headers=auth)
    assert repeated.status_code == 201
    assert repeated.json()["created"] is False
    assert repeated.json()["task_count"] == linked.json()["task_count"]

    plans = client.get("/api/v1/crop-planning/plans", headers=auth).json()
    assert plans[0]["calendar_task_count"] == linked.json()["task_count"]
