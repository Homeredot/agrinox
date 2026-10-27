def test_profile_details_can_be_updated(client, auth):
    before = client.get("/api/v1/auth/me", headers=auth)
    assert before.status_code == 200
    assert before.json()["created_at"]

    response = client.patch(
        "/api/v1/auth/me",
        headers=auth,
        json={"full_name": "Mukamana Alice", "email": "alice@example.com", "phone": "+250788000000", "location": "Musanze, Rwanda", "bio": "I grow potatoes."},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Mukamana Alice"
    assert response.json()["email"] == "alice@example.com"
    assert response.json()["phone"] == "+250788000000"
    assert response.json()["location"] == "Musanze, Rwanda"
    assert response.json()["bio"] == "I grow potatoes."


def test_profile_vector_avatar_can_be_selected(client, auth):
    response = client.patch(
        "/api/v1/auth/me", headers=auth, json={"avatar_key": "wheat", "avatar_color": "sunrise"}
    )
    assert response.status_code == 200
    assert response.json()["avatar_kind"] == "vector"
    assert response.json()["avatar_key"] == "wheat"
    assert response.json()["avatar_color"] == "sunrise"


def test_profile_photo_upload_is_private_and_can_be_removed(client, auth):
    from io import BytesIO
    from PIL import Image

    content = BytesIO()
    Image.new("RGB", (80, 60), "green").save(content, format="PNG")
    uploaded = client.post(
        "/api/v1/auth/me/avatar", headers=auth,
        files={"image": ("profile.png", content.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["avatar_kind"] == "photo"
    assert uploaded.json()["has_profile_photo"] is True
    assert client.get("/api/v1/auth/me/avatar").status_code == 401
    image = client.get("/api/v1/auth/me/avatar", headers=auth)
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"

    removed = client.delete("/api/v1/auth/me/avatar", headers=auth)
    assert removed.status_code == 200
    assert removed.json()["avatar_kind"] == "vector"
    assert removed.json()["has_profile_photo"] is False


def test_profile_photo_rejects_non_image_file(client, auth):
    response = client.post(
        "/api/v1/auth/me/avatar", headers=auth,
        files={"image": ("profile.jpg", b"not an image", "image/jpeg")},
    )
    assert response.status_code == 400


def test_profile_rejects_an_email_that_is_already_used(client, auth):
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "full_name": "Other Farmer", "password": "securepass"},
    )
    response = client.patch(
        "/api/v1/auth/me", headers=auth, json={"email": "other@example.com"}
    )
    assert response.status_code == 409


def test_password_change_requires_current_password_and_updates_login(client, auth):
    incorrect = client.post(
        "/api/v1/auth/me/password",
        headers=auth,
        json={"current_password": "not-the-password", "new_password": "new-secure-pass"},
    )
    assert incorrect.status_code == 400

    changed = client.post(
        "/api/v1/auth/me/password",
        headers=auth,
        json={"current_password": "securepass", "new_password": "new-secure-pass"},
    )
    assert changed.status_code == 200
    assert changed.json()["changed"] is True
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "farmer@example.com", "password": "securepass"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "farmer@example.com", "password": "new-secure-pass"},
    ).status_code == 200
