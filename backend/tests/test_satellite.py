import json

from app.db.models import Farm, FarmField, User
from app.db.session import SessionLocal


def _mapped_field() -> int:
    with SessionLocal.begin() as db:
        user = db.query(User).filter(User.email == "farmer@example.com").one()
        farm = Farm(owner_id=user.id, name="Hill Farm", province="NORTH", district="Musanze", sector="Muhoza", cell="Ruhengeri", village="User confirmed", province_code=4, district_code=403, sector_code="040310", cell_code=4031001, village_code=403100101, latitude=-1.5, longitude=29.63)
        db.add(farm); db.flush()
        geometry = {"type": "Polygon", "coordinates": [[[29.629, -1.501], [29.631, -1.501], [29.631, -1.499], [29.629, -1.499], [29.629, -1.501]]]}
        field = FarmField(farm_id=farm.id, name="Potato field", area_m2=48000, area_source="map", boundary_geojson=json.dumps(geometry))
        db.add(field); db.flush()
        return field.id


def test_satellite_unconfigured_never_invents_measurements(client, auth):
    field_id = _mapped_field()
    response = client.post("/api/v1/satellite/dashboard", headers=auth, json={"field_id": field_id, "date_from": "2026-04-01", "date_to": "2026-10-01"})
    assert response.status_code == 200
    body = response.json()
    assert body["integration"]["configured"] is False
    assert body["latest"] is None
    assert body["trend"] == []
    assert body["simulated"] is False
    assert body["area"]["source_mode"] == "mapped_field"


def test_location_area_is_saved_and_used_as_searched_area(client, auth):
    saved = client.post("/api/v1/satellite/areas", headers=auth, json={"name": "Ruhengeri observation area", "latitude": -1.5, "longitude": 29.63, "radius_m": 250})
    assert saved.status_code == 201
    assert saved.json()["geometry"]["type"] == "Polygon"
    assert len(client.get("/api/v1/satellite/areas", headers=auth).json()) == 1
    response = client.post("/api/v1/satellite/dashboard", headers=auth, json={"latitude": -1.5, "longitude": 29.63, "radius_m": 250, "label": "Ruhengeri", "date_from": "2026-08-01", "date_to": "2026-10-01"})
    assert response.status_code == 200
    assert response.json()["area"]["source_mode"] == "searched_area"


def test_field_without_boundary_is_rejected(client, auth):
    with SessionLocal.begin() as db:
        user = db.query(User).filter(User.email == "farmer@example.com").one()
        farm = Farm(owner_id=user.id, name="Manual farm", province="NORTH", district="Musanze", sector="Muhoza", cell="Ruhengeri", village="User confirmed", province_code=4, district_code=403, sector_code="040310", cell_code=4031001, village_code=403100101)
        db.add(farm); db.flush()
        field = FarmField(farm_id=farm.id, name="Manual field", area_m2=1000, area_source="manual_estimate")
        db.add(field); db.flush(); field_id = field.id
    response = client.post("/api/v1/satellite/dashboard", headers=auth, json={"field_id": field_id, "date_from": "2026-09-01", "date_to": "2026-10-01"})
    assert response.status_code == 422
    assert "no drawn map boundary" in response.json()["detail"]
