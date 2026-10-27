def create_field(client, auth):
    farm = client.post("/api/v1/farms", headers=auth, json={
        "name": "Finance Farm", "province": "ignored", "district": "ignored", "sector": "ignored",
        "cell": "ignored", "village": "ignored", "province_code": 4, "district_code": 403,
        "sector_code": "040310", "cell_code": 4031001, "village_code": 403100101,
        "latitude": -1.499, "longitude": 29.634,
    }).json()
    return client.post(
        f"/api/v1/farms/{farm['id']}/fields", headers=auth,
        json={"name": "Half hectare", "crop_note": "Irish potato", "side_a": 100, "side_b": 50, "side_c": 100, "side_d": 50, "side_unit": "m"},
    ).json()


def test_financial_calculation_uses_entered_values(client, auth):
    response = client.post("/api/v1/finance/calculate", headers=auth, json={
        "area_ha": 0.5,
        "expected_harvest_kg": 5000,
        "selling_price_per_kg_rwf": 400,
        "expenses": [
            {"category": "seeds", "amount_rwf": 100000},
            {"category": "labor", "description": "Planting and harvest", "amount_rwf": 300000},
        ],
    })
    assert response.status_code == 200
    result = response.json()
    assert result["currency"] == "RWF"
    assert result["total_expenses_rwf"] == 400000
    assert result["expected_revenue_rwf"] == 2000000
    assert result["expected_profit_rwf"] == 1600000
    assert result["break_even_price_per_kg_rwf"] == 80
    assert result["cost_per_kg_rwf"] == 80
    assert result["profit_margin_percent"] == 80
    assert result["profit_per_hectare_rwf"] == 3200000
    assert result["price_source"] == "farmer_entered"
    assert [item["change_percent"] for item in result["price_scenarios"]] == [-20, -10, 0, 10, 20]


def test_financial_plan_and_actual_transactions_remain_separate(client, auth):
    field = create_field(client, auth)
    created = client.post("/api/v1/finance/plans", headers=auth, json={
        "field_id": field["id"], "title": "2026B potato budget", "crop": "Irish potato",
        "area_ha": 0.5, "expected_harvest_kg": 5000, "selling_price_per_kg_rwf": 400,
        "expenses": [{"category": "seeds", "amount_rwf": 100000}, {"category": "labor", "amount_rwf": 300000}],
    })
    assert created.status_code == 201
    plan = created.json()
    assert plan["planned"]["expected_profit_rwf"] == 1600000
    assert plan["actual"]["transaction_count"] == 0

    expense = client.post(f"/api/v1/finance/plans/{plan['id']}/transactions", headers=auth, json={
        "kind": "expense", "category": "seeds", "description": "Certified seed purchase",
        "amount_rwf": 120000, "occurred_on": "2026-10-20",
    })
    revenue = client.post(f"/api/v1/finance/plans/{plan['id']}/transactions", headers=auth, json={
        "kind": "revenue", "category": "crop_sale", "description": "First potato sale",
        "amount_rwf": 900000, "quantity_kg": 2000, "occurred_on": "2026-10-24",
    })
    assert expense.status_code == 201
    assert revenue.status_code == 201
    detail = client.get(f"/api/v1/finance/plans/{plan['id']}", headers=auth).json()
    assert detail["planned"]["total_expenses_rwf"] == 400000
    assert detail["actual"]["actual_expenses_rwf"] == 120000
    assert detail["actual"]["actual_revenue_rwf"] == 900000
    assert detail["actual"]["actual_profit_rwf"] == 780000
    assert detail["actual"]["average_realized_price_per_kg_rwf"] == 450


def test_finance_prefills_supported_crop_plan_without_inventing_price(client, auth):
    field = create_field(client, auth)
    crop_plan = client.post("/api/v1/crop-planning/plans", headers=auth, json={
        "field_id": field["id"], "crop": "Irish potato", "season": "B",
        "planned_planting_date": "2026-03-10", "irrigation": "available",
    }).json()
    options = client.get("/api/v1/finance/crop-plans", headers=auth).json()
    linked = next(item for item in options if item["id"] == crop_plan["plan_id"])
    assert linked["area_ha"] == 0.5
    assert linked["expected_harvest_range_kg"]
    assert linked["suggested_harvest_kg"] > 0
    assert "price" not in linked
