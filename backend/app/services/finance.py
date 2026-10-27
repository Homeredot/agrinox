from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CropPlan, FarmField, FinancialPlan, FinancialTransaction


EXPENSE_LABELS = {
    "seeds": "Seeds",
    "fertilizer": "Fertilizer",
    "labor": "Labor",
    "transport": "Transport",
    "irrigation": "Irrigation",
    "equipment": "Equipment",
    "land_preparation": "Land preparation",
    "pest_management": "Pest management",
    "other": "Other expenses",
}


def _money(value: float) -> float:
    return round(float(value), 2)


def calculate(area_ha: float, expected_harvest_kg: float, selling_price_per_kg_rwf: float, expenses: list[dict]) -> dict:
    normalized = [{
        "category": item["category"],
        "category_label": EXPENSE_LABELS[item["category"]],
        "description": item.get("description") or None,
        "amount_rwf": _money(item["amount_rwf"]),
    } for item in expenses]
    total_expenses = sum(item["amount_rwf"] for item in normalized)
    revenue = expected_harvest_kg * selling_price_per_kg_rwf
    profit = revenue - total_expenses
    break_even = total_expenses / expected_harvest_kg
    margin = (profit / revenue * 100) if revenue > 0 else None
    breakdown = []
    for key, label in EXPENSE_LABELS.items():
        amount = sum(item["amount_rwf"] for item in normalized if item["category"] == key)
        if amount:
            breakdown.append({"category": key, "label": label, "amount_rwf": _money(amount), "share_percent": round(amount / total_expenses * 100, 1) if total_expenses else 0})
    scenarios = []
    for percent in (-20, -10, 0, 10, 20):
        price = selling_price_per_kg_rwf * (1 + percent / 100)
        scenario_revenue = expected_harvest_kg * price
        scenarios.append({
            "label": "Entered price" if percent == 0 else f"{percent:+d}% price",
            "change_percent": percent,
            "price_per_kg_rwf": _money(price),
            "revenue_rwf": _money(scenario_revenue),
            "profit_rwf": _money(scenario_revenue - total_expenses),
        })
    return {
        "currency": "RWF",
        "area_ha": area_ha,
        "expected_harvest_kg": expected_harvest_kg,
        "selling_price_per_kg_rwf": selling_price_per_kg_rwf,
        "total_expenses_rwf": _money(total_expenses),
        "expected_revenue_rwf": _money(revenue),
        "expected_profit_rwf": _money(profit),
        "break_even_price_per_kg_rwf": _money(break_even),
        "cost_per_kg_rwf": _money(break_even),
        "profit_margin_percent": round(margin, 2) if margin is not None else None,
        "profit_per_hectare_rwf": _money(profit / area_ha),
        "expense_breakdown": breakdown,
        "price_scenarios": scenarios,
        "price_source": "farmer_entered",
        "method": "Revenue = expected harvest × entered selling price. Profit = revenue − itemized expenses.",
    }


def actual_summary(transactions: list[FinancialTransaction]) -> dict:
    expenses = sum(item.amount_rwf for item in transactions if item.kind == "expense")
    revenue = sum(item.amount_rwf for item in transactions if item.kind == "revenue")
    quantity = sum(item.quantity_kg or 0 for item in transactions if item.kind == "revenue")
    return {
        "actual_expenses_rwf": _money(expenses),
        "actual_revenue_rwf": _money(revenue),
        "actual_profit_rwf": _money(revenue - expenses),
        "actual_sold_quantity_kg": _money(quantity),
        "transaction_count": len(transactions),
        "average_realized_price_per_kg_rwf": _money(revenue / quantity) if quantity else None,
    }


def transaction_view(item: FinancialTransaction) -> dict:
    return {
        "id": item.id,
        "plan_id": item.plan_id,
        "kind": item.kind,
        "category": item.category,
        "category_label": EXPENSE_LABELS.get(item.category, item.category.replace("_", " ").title()),
        "description": item.description,
        "amount_rwf": item.amount_rwf,
        "quantity_kg": item.quantity_kg,
        "occurred_on": item.occurred_on.isoformat(),
        "created_at": item.created_at.isoformat(),
    }


def plan_query(owner_id: int):
    return (
        select(FinancialPlan)
        .where(FinancialPlan.owner_id == owner_id)
        .options(
            selectinload(FinancialPlan.field).selectinload(FarmField.farm),
            selectinload(FinancialPlan.transactions),
        )
    )


def get_plan(db: Session, owner_id: int, plan_id: int) -> FinancialPlan | None:
    return db.scalar(plan_query(owner_id).where(FinancialPlan.id == plan_id))


def plan_view(plan: FinancialPlan) -> dict:
    transactions = sorted(plan.transactions, key=lambda item: (item.occurred_on, item.id), reverse=True)
    return {
        "id": plan.id,
        "field_id": plan.field_id,
        "field_name": plan.field.name,
        "farm_name": plan.field.farm.name,
        "crop_plan_id": plan.crop_plan_id,
        "title": plan.title,
        "crop": plan.crop,
        "area_ha": plan.area_ha,
        "expected_harvest_kg": plan.expected_harvest_kg,
        "selling_price_per_kg_rwf": plan.selling_price_per_kg_rwf,
        "expenses": json.loads(plan.expenses_json),
        "planned": json.loads(plan.result_json),
        "actual": actual_summary(transactions),
        "transactions": [transaction_view(item) for item in transactions],
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat(),
    }


def list_plans(db: Session, owner_id: int) -> list[dict]:
    plans = db.scalars(plan_query(owner_id).order_by(FinancialPlan.updated_at.desc())).all()
    return [plan_view(plan) for plan in plans]


def crop_plan_options(db: Session, owner_id: int) -> list[dict]:
    plans = db.scalars(
        select(CropPlan)
        .where(CropPlan.owner_id == owner_id)
        .options(selectinload(CropPlan.field).selectinload(FarmField.farm))
        .order_by(CropPlan.created_at.desc())
    ).all()
    result = []
    for plan in plans:
        prediction = json.loads(plan.result_json)
        harvest_range_t = (prediction.get("prediction") or {}).get("estimated_total_harvest_t")
        harvest_range_kg = [round(value * 1000, 2) for value in harvest_range_t] if harvest_range_t else None
        result.append({
            "id": plan.id,
            "field_id": plan.field_id,
            "field_name": plan.field.name,
            "farm_name": plan.field.farm.name,
            "crop": plan.crop,
            "season": plan.season,
            "planned_planting_date": plan.planned_planting_date.isoformat(),
            "area_ha": round(plan.field.area_m2 / 10000, 4),
            "expected_harvest_range_kg": harvest_range_kg,
            "suggested_harvest_kg": round(sum(harvest_range_kg) / 2, 2) if harvest_range_kg else None,
            "evidence_available": bool(harvest_range_kg),
            "note": "Editable midpoint of the supported prediction range." if harvest_range_kg else "No numerical harvest prediction is available; enter your own estimate.",
        })
    return result
