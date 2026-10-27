from app.core.config import settings
from app.services import notifications


def test_notification_preferences_test_email_and_history(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "email_enabled", True)
    monkeypatch.setattr(settings, "email_host", "smtp.example.test")
    monkeypatch.setattr(settings, "email_user", "sender@example.test")
    monkeypatch.setattr(settings, "email_pass", "app-password")
    sent = []
    monkeypatch.setattr(notifications, "_send_smtp", lambda recipient, subject, body: sent.append((recipient, subject, body)))

    response = client.get("/api/v1/notifications/settings", headers=auth)
    assert response.status_code == 200
    assert response.json()["email_configured"] is True
    assert response.json()["irrigation_events"] is True

    response = client.put("/api/v1/notifications/settings", headers=auth, json={"finance_updates": False})
    assert response.status_code == 200
    assert response.json()["finance_updates"] is False

    response = client.post("/api/v1/notifications/test", headers=auth)
    assert response.status_code == 200
    assert response.json()["sent"] is True
    assert sent and sent[0][0] == "farmer@example.com"

    history = client.get("/api/v1/notifications/history", headers=auth).json()
    assert len(history) == 1
    assert history[0]["status"] == "sent"
    assert "test" in history[0]["subject"].lower()


def test_notification_test_reports_not_configured(client, auth):
    response = client.post("/api/v1/notifications/test", headers=auth)
    assert response.status_code == 200
    assert response.json() == {"status": "not_configured", "sent": False}

    notifications = client.get("/api/v1/notifications", headers=auth)
    assert notifications.status_code == 200
    assert any(item["title"] == "Agrinox email test" for item in notifications.json())


def test_notification_center_read_state(client, auth):
    initial = client.get("/api/v1/notifications", headers=auth)
    assert initial.status_code == 200

    client.post("/api/v1/notifications/test", headers=auth)
    items = client.get("/api/v1/notifications", headers=auth).json()
    unread = [item for item in items if not item["is_read"]]
    assert unread

    count = client.get("/api/v1/notifications/unread-count", headers=auth)
    assert count.status_code == 200
    assert count.json()["unread"] == len(unread)

    marked = client.patch(f"/api/v1/notifications/{unread[0]['id']}/read", headers=auth)
    assert marked.status_code == 200
    assert marked.json()["is_read"] is True

    cleared = client.post("/api/v1/notifications/read-all", headers=auth)
    assert cleared.status_code == 200
    assert client.get("/api/v1/notifications/unread-count", headers=auth).json()["unread"] == 0
