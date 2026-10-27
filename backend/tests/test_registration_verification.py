from app.core.config import settings


def test_new_account_requires_email_code_when_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "email_verification_required", True)
    monkeypatch.setattr(
        "app.services.two_factor.send_notification",
        lambda *args, **kwargs: {"status": "sent", "sent": True},
    )
    monkeypatch.setattr("app.services.two_factor.secrets.randbelow", lambda _limit: 123456)

    created = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newfarmer@example.com",
            "full_name": "New Farmer",
            "password": "securepass",
        },
    )
    assert created.status_code == 201
    challenge = created.json()
    assert challenge["email_verification_required"] is True
    assert "access_token" not in challenge

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "newfarmer@example.com", "password": "securepass"},
    )
    assert blocked.status_code == 403

    verified = client.post(
        "/api/v1/auth/register/verify",
        json={"challenge_token": challenge["challenge_token"], "code": "123456"},
    )
    assert verified.status_code == 200
    assert verified.json()["access_token"]

    signed_in = client.post(
        "/api/v1/auth/login",
        json={"email": "newfarmer@example.com", "password": "securepass"},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["access_token"]
