from app.services.two_factor import totp_code


def test_authenticator_setup_login_and_disable(client, auth):
    setup = client.post(
        "/api/v1/auth/2fa/setup/authenticator",
        headers=auth,
        json={"current_password": "securepass"},
    )
    assert setup.status_code == 200
    details = setup.json()
    assert details["qr_code_data_url"].startswith("data:image/png;base64,")
    assert details["secret"]

    enabled = client.post(
        "/api/v1/auth/2fa/setup/confirm",
        headers=auth,
        json={"challenge_token": details["challenge_token"], "code": totp_code(details["secret"])},
    )
    assert enabled.status_code == 200
    assert enabled.json()["method"] == "authenticator"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "farmer@example.com", "password": "securepass"},
    )
    assert login.status_code == 200
    challenge = login.json()
    assert challenge["two_factor_required"] is True
    assert "access_token" not in challenge

    verified = client.post(
        "/api/v1/auth/2fa/login/verify",
        json={"challenge_token": challenge["challenge_token"], "code": totp_code(details["secret"])},
    )
    assert verified.status_code == 200
    assert verified.json()["access_token"]

    disable = client.post(
        "/api/v1/auth/2fa/disable/start",
        headers=auth,
        json={"current_password": "securepass"},
    ).json()
    disabled = client.post(
        "/api/v1/auth/2fa/disable/confirm",
        headers=auth,
        json={"challenge_token": disable["challenge_token"], "code": totp_code(details["secret"])},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


def test_email_setup_and_login_code(client, auth, monkeypatch):
    monkeypatch.setattr("app.services.two_factor.send_notification", lambda *args, **kwargs: {"status": "sent", "sent": True})
    monkeypatch.setattr("app.services.two_factor.secrets.randbelow", lambda _limit: 123456)

    setup = client.post(
        "/api/v1/auth/2fa/setup/email",
        headers=auth,
        json={"current_password": "securepass"},
    )
    assert setup.status_code == 200
    enabled = client.post(
        "/api/v1/auth/2fa/setup/confirm",
        headers=auth,
        json={"challenge_token": setup.json()["challenge_token"], "code": "123456"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["method"] == "email"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "farmer@example.com", "password": "securepass"},
    ).json()
    assert login["masked_email"].endswith("@example.com")
    verified = client.post(
        "/api/v1/auth/2fa/login/verify",
        json={"challenge_token": login["challenge_token"], "code": "123456"},
    )
    assert verified.status_code == 200


def test_two_factor_rejects_wrong_password_and_reused_code(client, auth):
    assert client.post(
        "/api/v1/auth/2fa/setup/authenticator",
        headers=auth,
        json={"current_password": "wrong-password"},
    ).status_code == 400

    setup = client.post(
        "/api/v1/auth/2fa/setup/authenticator",
        headers=auth,
        json={"current_password": "securepass"},
    ).json()
    payload = {"challenge_token": setup["challenge_token"], "code": totp_code(setup["secret"])}
    assert client.post("/api/v1/auth/2fa/setup/confirm", headers=auth, json=payload).status_code == 200
    assert client.post("/api/v1/auth/2fa/setup/confirm", headers=auth, json=payload).status_code == 401
