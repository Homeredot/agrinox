def test_district_options_are_validated_aggregate_dimensions(client, auth):
    response = client.get("/api/v1/district-intelligence/options", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["coverage"]["districts"] == 30
    assert body["years"] == [2026, 2025, 2024]
    assert {item["category"] for item in body["indicators"]} == {"crop", "land", "irrigation", "practice"}


def test_musanze_published_yield_and_privacy_separation(client, auth):
    response = client.get(
        "/api/v1/district-intelligence/dashboard",
        params={"year": 2026, "season": "A", "province": "Northern Province", "district": "Musanze", "crop": "Irish potato", "indicator": "yield"},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["value"] == 12.556062
    assert body["summary"]["unit"] == "metric tonnes/ha"
    assert body["private_farm_aggregate"]["included"] is False
    assert "at least 5 farms" in body["private_farm_aggregate"]["disclosure_rule"]


def test_district_boundaries_and_exports(client, auth):
    boundaries = client.get("/api/v1/district-intelligence/boundaries", headers=auth)
    assert boundaries.status_code == 200
    assert len(boundaries.json()["features"]) == 30
    params = {"year": 2026, "season": "B", "province": "City of Kigali", "crop": "Maize", "indicator": "production"}
    csv_response = client.get("/api/v1/district-intelligence/export.csv", params=params, headers=auth)
    assert csv_response.status_code == 200
    assert csv_response.content.startswith(b"\xef\xbb\xbfyear,season")
    pdf_response = client.get("/api/v1/district-intelligence/export.pdf", params=params, headers=auth)
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF")


def test_missing_older_district_data_is_reported_not_invented(client, auth):
    response = client.get(
        "/api/v1/district-intelligence/dashboard",
        params={"year": 2025, "season": "A", "province": "Northern Province", "district": "Musanze", "crop": "Maize", "indicator": "production"},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["value"] is None
    assert body["summary"]["records"] == 0
