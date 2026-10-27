import json
import math
from pathlib import Path
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CropPlan, Farm, FarmField, SoilReading


DATA = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "nisr_yield_observations.json").read_text(encoding="utf-8")
)
OBSERVATIONS = DATA["observations"]
SOURCES = DATA["sources"]
MODEL_VERSION = "nisr-historical-baseline-v1.0"
MIN_ML_OBSERVATIONS = 20


def _round(value: float | None, digits: int = 2):
    return None if value is None else round(value, digits)


def planning_options() -> dict:
    crops = sorted({item["crop"] for item in OBSERVATIONS})
    coverage = {}
    for crop in crops:
        coverage[crop] = sorted({item["season"] for item in OBSERVATIONS if item["crop"] == crop})
    return {
        "crops": crops,
        "seasons": [
            {"value": "A", "label": "Season A", "usual_months": "September–February"},
            {"value": "B", "label": "Season B", "usual_months": "March–June"},
            {"value": "C", "label": "Season C", "usual_months": "July–September"},
        ],
        "coverage_by_crop": coverage,
        "dataset_version": DATA["dataset_version"],
        "model_version": MODEL_VERSION,
        "minimum_observations_for_ml": MIN_ML_OBSERVATIONS,
        "sources": list(SOURCES.values()),
    }


def _time_ordered_baseline_validation(observations: list[dict]) -> dict:
    ordered = sorted(observations, key=lambda item: item["year"])
    errors = []
    folds = []
    for index in range(1, len(ordered)):
        training = ordered[:index]
        test = ordered[index]
        predicted = mean(item["yield_t_ha"] for item in training)
        error = test["yield_t_ha"] - predicted
        errors.append(error)
        folds.append({
            "train_years": [item["year"] for item in training],
            "test_year": test["year"],
            "predicted_t_ha": _round(predicted, 3),
            "observed_t_ha": test["yield_t_ha"],
        })
    if not errors:
        return {
            "mae_t_ha": None,
            "rmse_t_ha": None,
            "validation_design": "Not enough time-ordered observations for a held-out test.",
            "folds": [],
        }
    return {
        "mae_t_ha": _round(mean(abs(error) for error in errors), 3),
        "rmse_t_ha": _round(math.sqrt(mean(error * error for error in errors)), 3),
        "validation_design": (
            "Expanding-window backtest: each year is predicted only from earlier years. "
            "No record is used for both training and testing in the same fold, and no future year is used."
        ),
        "folds": folds,
    }


def _season_date_note(season: str, month: int) -> str | None:
    allowed = {"A": {9, 10, 11, 12, 1, 2}, "B": {3, 4, 5, 6}, "C": {7, 8, 9}}
    if month in allowed[season]:
        return None
    return f"The selected planting month is outside NISR's usual Season {season} window; confirm timing locally."


def _soil_snapshot(db: Session, field_id: int) -> list[dict]:
    readings = db.scalars(
        select(SoilReading)
        .where(SoilReading.field_id == field_id)
        .order_by(SoilReading.measurement_type, SoilReading.measured_at.desc())
    ).all()
    latest = {}
    for reading in readings:
        latest.setdefault(reading.measurement_type, reading)
    return [{
        "measurement": key,
        "value": reading.value,
        "unit": reading.unit,
        "reliability": reading.reliability,
        "calibration_status": reading.calibration_status,
        "measured_at": reading.measured_at.isoformat(),
    } for key, reading in sorted(latest.items())]


def recommend_crops(db: Session, owner_id: int, field: FarmField, season: str, planting_date) -> dict:
    """Rank only choices supported by curated observations; never claim biological suitability."""
    farm = field.farm
    area_ha = field.area_m2 / 10000
    plans = db.scalars(
        select(CropPlan)
        .where(CropPlan.owner_id == owner_id, CropPlan.field_id == field.id)
        .order_by(CropPlan.planned_planting_date.desc(), CropPlan.created_at.desc())
    ).all()
    recorded_crops = [plan.crop for plan in plans]
    fallback_crop = field.crop_note or (field.soil_context.crop_type if field.soil_context else None)
    last_crop = recorded_crops[0] if recorded_crops else fallback_crop
    date_note = _season_date_note(season, planting_date.month)
    candidates = []

    for crop in sorted({item["crop"] for item in OBSERVATIONS if item["season"] == season}):
        national = sorted([
            item for item in OBSERVATIONS
            if item["crop"] == crop and item["season"] == season and item["geography"] == "Rwanda"
        ], key=lambda item: item["year"])
        district = sorted([
            item for item in OBSERVATIONS
            if item["crop"] == crop and item["season"] == season
            and item["geography"].casefold() == farm.district.casefold()
        ], key=lambda item: item["year"])
        if len(national) < 2:
            continue

        observed_yields = [item["yield_t_ha"] for item in national + district]
        lower, upper = min(observed_yields), max(observed_yields)
        baseline = median(item["yield_t_ha"] for item in national)
        repeated = bool(last_crop and crop.casefold() == last_crop.casefold())
        score = min(len(national), 5) * 10 + min(len(district), 2) * 12 - (18 if repeated else 0)
        source_keys = {item["source"] for item in national + district}
        why = [
            (
                f"Uses {len(district)} {farm.district} record(s) plus {len(national)} Rwanda records."
                if district else
                f"Uses {len(national)} verified Rwanda records; no {farm.district} series is available."
            ),
            f"For this {area_ha:.3f} ha field, the observed-data harvest range is {lower * area_ha:.2f}–{upper * area_ha:.2f} tonnes.",
        ]
        if last_crop:
            why.append(
                f"{crop} is the last recorded crop; confirm rotation and pest history before repeating it."
                if repeated else
                f"The last recorded crop was {last_crop}; this option avoids automatically repeating it."
            )
        else:
            why.append("No previous crop is recorded, so rotation history could not affect the ranking.")

        candidates.append({
            "crop": crop,
            "score": score,
            "yield_range_t_ha": [_round(lower, 3), _round(upper, 3)],
            "estimated_total_harvest_t": [_round(lower * area_ha, 3), _round(upper * area_ha, 3)],
            "historical_baseline_t_ha": _round(baseline, 3),
            "district_observations": len(district),
            "national_observations": len(national),
            "years": [item["year"] for item in national],
            "history_check": "repeat_needs_review" if repeated else ("different_from_last" if last_crop else "history_missing"),
            "why": why,
            "sources": [{"key": key, **SOURCES[key]} for key in sorted(source_keys)],
        })

    candidates.sort(key=lambda item: (-item["score"], item["crop"]))
    for index, item in enumerate(candidates[:3]):
        item["rank"] = index + 1
        item["label"] = "Best-supported choice" if index == 0 else "Alternative"
        item.pop("score", None)

    history = [{
        "crop": plan.crop,
        "season": plan.season,
        "planned_planting_date": plan.planned_planting_date.isoformat(),
    } for plan in plans[:5]]
    if not history and fallback_crop:
        history.append({"crop": fallback_crop, "season": None, "planned_planting_date": None})

    return {
        "field": {
            "id": field.id,
            "name": field.name,
            "farm_name": farm.name,
            "district": farm.district,
            "province": farm.province,
            "area_ha": _round(area_ha, 4),
        },
        "season": season,
        "planned_planting_date": planting_date.isoformat(),
        "timing_note": date_note,
        "last_recorded_crop": last_crop,
        "crop_history": history,
        "recommendations": candidates[:3],
        "method": (
            "Ranks crops by verified NISR observation coverage, available district evidence, and whether the field's last recorded crop would be repeated."
        ),
        "important_note": (
            "These are the best-supported planning choices in the available data, not a guarantee that a crop is agronomically or financially best. "
            "Confirm seed, market, soil, water, pest and rotation suitability with a local agronomist before planting."
        ),
        "rotation_reference": {
            "title": "FAO: Species diversification and crop rotation",
            "url": "https://www.fao.org/conservation-agriculture/in-practice/species-diversification/en/",
        },
    }


def build_prediction(db: Session, field: FarmField, payload) -> dict:
    farm = field.farm
    area_ha = field.area_m2 / 10000
    national = sorted([
        item for item in OBSERVATIONS
        if item["crop"] == payload.crop and item["season"] == payload.season and item["geography"] == "Rwanda"
    ], key=lambda item: item["year"])
    district = sorted([
        item for item in OBSERVATIONS
        if item["crop"] == payload.crop and item["season"] == payload.season
        and item["geography"].casefold() == farm.district.casefold()
    ], key=lambda item: item["year"])
    source_keys = {item["source"] for item in national + district}
    source_refs = [{"key": key, **SOURCES[key]} for key in sorted(source_keys)]
    soil = _soil_snapshot(db, field.id)
    context = {
        "farm_id": farm.id,
        "farm_name": farm.name,
        "field_id": field.id,
        "field_name": field.name,
        "province": farm.province,
        "district": farm.district,
        "area_ha": _round(area_ha, 4),
        "area_source": field.area_source,
        "existing_crop_note": field.crop_note,
        "soil_context": {
            "crop_type": field.soil_context.crop_type if field.soil_context else None,
            "growth_stage": field.soil_context.growth_stage if field.soil_context else None,
        },
        "latest_soil_measurements": soil,
    }
    limitations = [
        "This is a statistical planning baseline, not a guarantee for an individual field.",
        "Published survey yields do not encode this field's seed variety, management, pests, or future weather.",
        "Soil and irrigation details are shown as context but are not converted into unsupported numerical yield adjustments.",
    ]
    date_note = _season_date_note(payload.season, payload.planned_planting_date.month)
    if date_note:
        limitations.append(date_note)

    if len(national) < 2:
        return {
            "status": "insufficient_evidence",
            "message": (
                f"There are only {len(national)} verified national observations for {payload.crop}, Season {payload.season}. "
                "A yield range is not calculated."
            ),
            "context": context,
            "inputs": payload.model_dump(mode="json"),
            "data_availability": {
                "district_observations": len(district),
                "national_observations": len(national),
                "years": [item["year"] for item in national],
                "broader_baseline_used": False,
            },
            "model": {
                "version": MODEL_VERSION,
                "type": "No numerical model",
                "ml_status": "not_trained",
                "reason": "Fewer than two compatible verified observations.",
            },
            "limitations": limitations,
            "sources": source_refs,
        }

    yields = [item["yield_t_ha"] for item in national]
    if district:
        yields.extend(item["yield_t_ha"] for item in district)
    lower, upper = min(yields), max(yields)
    baseline = median(item["yield_t_ha"] for item in national)
    validation = _time_ordered_baseline_validation(national)
    spread_ratio = (upper - lower) / baseline if baseline else 1
    confidence = "moderate" if len(national) >= 4 and spread_ratio <= 0.25 else "low"
    factors = [
        {
            "factor": "Crop and season",
            "effect": f"Baseline uses {len(national)} NISR {payload.crop} observations for Season {payload.season}.",
        },
        {
            "factor": "Field area",
            "effect": f"Recorded field area {area_ha:.3f} ha scales the per-hectare range into total harvest.",
        },
        {
            "factor": "Geography",
            "effect": (
                f"{len(district)} verified {farm.district} observation(s) bound the range; the centre remains the national historical median."
                if district else
                f"No compatible {farm.district} series is curated yet, so the result uses a clearly labeled Rwanda national baseline."
            ),
        },
        {
            "factor": "Field context",
            "effect": (
                f"{len(soil)} latest soil measurement(s), irrigation={payload.irrigation}, and previous crop={payload.previous_crop or 'not provided'} are recorded but not used as unvalidated multipliers."
            ),
        },
    ]
    return {
        "status": "baseline_available",
        "context": context,
        "inputs": payload.model_dump(mode="json"),
        "prediction": {
            "yield_range_t_ha": [_round(lower, 3), _round(upper, 3)],
            "estimated_total_harvest_t": [_round(lower * area_ha, 3), _round(upper * area_ha, 3)],
            "historical_baseline_t_ha": _round(baseline, 3),
            "confidence": confidence,
            "uncertainty": (
                "Range is the minimum to maximum of compatible published observations, including an exact district observation when available. "
                "It is not a probabilistic confidence interval."
            ),
        },
        "data_availability": {
            "district_observations": len(district),
            "national_observations": len(national),
            "years": [item["year"] for item in national],
            "geography_used": "district anchor plus Rwanda baseline" if district else "Rwanda national baseline",
            "broader_baseline_used": not bool(district),
            "observations": national + district,
        },
        "model": {
            "version": MODEL_VERSION,
            "type": "Transparent historical median and observed range",
            "mae_t_ha": validation["mae_t_ha"],
            "rmse_t_ha": validation["rmse_t_ha"],
            "validation_design": validation["validation_design"],
            "validation_folds": validation["folds"],
            "training_data_coverage": f"{len(national)} national observations, {min(item['year'] for item in national)}–{max(item['year'] for item in national)}, Season {payload.season}",
            "ml_status": "not_trained",
            "ml_reason": (
                f"Only {len(national)} compatible independent observations are available; at least {MIN_ML_OBSERVATIONS} are required before comparing regression models."
            ),
            "candidate_models": ["Random Forest", "Gradient Boosting"],
        },
        "major_influencing_factors": factors,
        "why_this_prediction": [factor["effect"] for factor in factors],
        "limitations": limitations,
        "sources": source_refs,
    }


def save_plan(db: Session, owner_id: int, field: FarmField, payload) -> dict:
    result = build_prediction(db, field, payload)
    plan = CropPlan(
        owner_id=owner_id,
        field_id=field.id,
        crop=payload.crop,
        season=payload.season,
        planned_planting_date=payload.planned_planting_date,
        irrigation=payload.irrigation,
        previous_crop=payload.previous_crop,
        previous_harvest_tonnes=payload.previous_harvest_tonnes,
        soil_notes=payload.soil_notes,
        result_json=json.dumps(result),
    )
    db.add(plan)
    db.flush()
    result["plan_id"] = plan.id
    plan.result_json = json.dumps(result)
    db.commit()
    return result


def list_plans(db: Session, owner_id: int) -> list[dict]:
    plans = db.scalars(
        select(CropPlan)
        .where(CropPlan.owner_id == owner_id)
        .options(selectinload(CropPlan.field).selectinload(FarmField.farm), selectinload(CropPlan.calendar_tasks))
        .order_by(CropPlan.created_at.desc())
    ).all()
    return [{
        "id": plan.id,
        "crop": plan.crop,
        "season": plan.season,
        "planned_planting_date": plan.planned_planting_date.isoformat(),
        "farm_name": plan.field.farm.name,
        "field_name": plan.field.name,
        "district": plan.field.farm.district,
        "created_at": plan.created_at.isoformat(),
        "calendar_task_count": len(plan.calendar_tasks),
        "result": json.loads(plan.result_json),
    } for plan in plans]
