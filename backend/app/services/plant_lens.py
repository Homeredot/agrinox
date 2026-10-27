import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import PlantLensCase


BACKEND_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = BACKEND_ROOT / "uploads" / "plant_lens"
SUPPORTED_CROPS = [
    {"id": "irish-potato", "name": "Irish potato", "model_supported": True},
    {"id": "tomato", "name": "Tomato", "model_supported": True},
]
CROP_NAMES = {item["id"]: item["name"] for item in SUPPORTED_CROPS}
MODEL_CONFIG = {
    "irish-potato": (settings.plant_lens_model_path, settings.plant_lens_model_version),
    "tomato": (settings.plant_lens_tomato_model_path, settings.plant_lens_tomato_model_version),
}
POTATO_CLASS_DETAILS = {
    "early blight": {
        "condition": "Possible early blight pattern",
        "visible_symptoms": ["Brown lesions that may show concentric ring patterns", "Yellowing around older leaf lesions"],
        "inspection_steps": ["Photograph both sides of several affected leaves", "Check whether older lower leaves were affected first", "Compare symptoms across several plants, not one leaf"],
    },
    "late blight": {
        "condition": "Possible late blight pattern",
        "visible_symptoms": ["Irregular water-soaked or dark brown leaf lesions", "Possible pale or white growth around lesion edges on the leaf underside in humid conditions"],
        "inspection_steps": ["Inspect leaf undersides early in the morning", "Check stems and nearby plants for rapidly expanding dark lesions", "Seek prompt expert confirmation because late blight can progress quickly"],
    },
    "healthy": {
        "condition": "No supported blight pattern detected",
        "visible_symptoms": ["The image does not strongly match early- or late-blight classes in this model"],
        "inspection_steps": ["Inspect the whole plant for wilting, pests or symptoms outside the photographed leaf", "Retake a sharp image in natural light if symptoms remain concerning"],
    },
}
TOMATO_CLASS_DETAILS = {
    "tomato leaf spot pattern": {"condition": "Possible tomato leaf-spot pattern", "visible_symptoms": ["Spots or lesions are visible, but several tomato conditions can look alike in a photograph", "The exact cause cannot be separated safely from this image alone"], "inspection_steps": ["Photograph both sides of several affected leaves", "Note whether symptoms started on lower or upper growth", "Ask an agronomist to distinguish bacterial spot, early blight, Septoria and target spot before treatment"]},
    "bacterial spot": {"condition": "Possible bacterial spot pattern", "visible_symptoms": ["Small dark leaf spots, sometimes with yellow margins", "Spots may join as damage increases"], "inspection_steps": ["Check several leaves and any fruit for small raised spots", "Photograph both sides of affected leaves", "Request expert confirmation before choosing treatment"]},
    "early blight": {"condition": "Possible tomato early blight pattern", "visible_symptoms": ["Brown spots that may show concentric rings", "Older lower leaves may yellow around lesions"], "inspection_steps": ["Check whether symptoms began on older lower leaves", "Inspect stems and fruit for dark lesions", "Compare symptoms on several plants"]},
    "late blight": {"condition": "Possible tomato late blight pattern", "visible_symptoms": ["Irregular water-soaked or dark leaf lesions", "Pale growth may appear on leaf undersides in humid weather"], "inspection_steps": ["Inspect leaf undersides in the morning", "Check stems and nearby plants for rapidly expanding lesions", "Seek prompt expert confirmation"]},
    "leaf mold": {"condition": "Possible tomato leaf mold pattern", "visible_symptoms": ["Yellow patches on upper leaf surfaces", "Olive or brown velvety growth may appear underneath"], "inspection_steps": ["Inspect the underside of affected leaves", "Note greenhouse or high-humidity conditions", "Compare several leaves before requesting expert review"]},
    "septoria leaf spot": {"condition": "Possible Septoria leaf spot pattern", "visible_symptoms": ["Many small circular spots with pale centers and dark borders", "Lower leaves are often affected first"], "inspection_steps": ["Use a close photograph to show spot centers", "Check lower leaves on several plants", "Seek expert confirmation because other spots can look similar"]},
    "spider mites": {"condition": "Possible spider-mite stress pattern", "visible_symptoms": ["Fine pale stippling or bronzing on leaves", "Fine webbing may be visible on leaf undersides"], "inspection_steps": ["Inspect leaf undersides with a magnifier", "Look for tiny moving mites or webbing", "Confirm the pest before applying any control"]},
    "target spot": {"condition": "Possible target spot pattern", "visible_symptoms": ["Brown circular lesions that may show ring-like zones", "Lesions may enlarge and merge"], "inspection_steps": ["Photograph several lesions closely", "Check leaves, stems and fruit", "Request expert comparison with early blight and bacterial spot"]},
    "tomato mosaic virus": {"condition": "Possible tomato mosaic virus pattern", "visible_symptoms": ["Mottled light and dark green leaf pattern", "Leaves may be distorted or narrowed"], "inspection_steps": ["Check new growth for repeated mosaic patterns", "Compare affected and unaffected plants", "Seek expert confirmation; an image alone cannot confirm a virus"]},
    "tomato yellow leaf curl virus": {"condition": "Possible tomato yellow leaf curl virus pattern", "visible_symptoms": ["Upward leaf curling with yellowing", "New growth may be small or stunted"], "inspection_steps": ["Check young upper leaves and overall plant stunting", "Look for whiteflies without assuming they prove the disease", "Seek expert or laboratory confirmation"]},
    "healthy": {"condition": "No supported tomato condition detected", "visible_symptoms": ["The image does not strongly match the supported tomato disease or pest classes"], "inspection_steps": ["Inspect the full plant for symptoms outside the photographed leaf", "Retake a sharp image if the plant still appears unhealthy"]},
}
CLASS_DETAILS = {"irish-potato": POTATO_CLASS_DETAILS, "tomato": TOMATO_CLASS_DETAILS}
MODEL_SOURCE = {
    "title": "disease_dataset plant disease image dataset (Kaggle)",
    "url": "https://www.kaggle.com/datasets/emmarex/plantdisease/",
}
TRAINING_WORKFLOW_SOURCE = {
    "title": "FastAI plant disease workflow referenced for this module",
    "url": "https://www.kaggle.com/code/eshitanandy/image-processing-plant-disease-detection-fastai",
}
SYMPTOM_SOURCE = {
    "title": "International Potato Center: Potato late blight technical guidance",
    "url": "https://cipotato.org/publication/potato-late-blight-technical-manual-2/",
}

_learners: dict[str, object] = {}
_learner_errors: dict[str, str] = {}
_learner_lock = threading.Lock()
MIN_ACCEPTED_CONFIDENCE = 0.70
MIN_ACCEPTED_MARGIN = 0.15
CROP_THRESHOLDS = {"irish-potato": (0.70, 0.15), "tomato": (0.90, 0.30)}
TOMATO_SPOT_LABELS = {"bacterial spot", "early blight", "septoria leaf spot", "target spot"}
# disease_dataset scores are not field accuracy. These deliberately conservative
# gates favour "uncertain" over a confident-looking, potentially wrong result.
TOMATO_CLASS_THRESHOLDS = {
    "late blight": (0.85, 0.25),
    "leaf mold": (0.80, 0.30),
    "spider mites": (0.90, 0.30),
    "tomato mosaic virus": (0.98, 0.50),
    "tomato yellow leaf curl virus": (0.90, 0.35),
    "healthy": (0.98, 0.50),
    "unsupported": (0.90, 0.35),
}


class ImageQualityError(ValueError):
    pass


def _model_path(crop_id: str = "irish-potato") -> Path:
    configured = Path(MODEL_CONFIG[crop_id][0])
    return configured if configured.is_absolute() else BACKEND_ROOT / configured


def _model_metadata(crop_id: str = "irish-potato") -> dict:
    metadata_path = _model_path(crop_id).with_suffix(".metadata.json")
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _model_version(crop_id: str = "irish-potato") -> str:
    return str(_model_metadata(crop_id).get("model_version") or MODEL_CONFIG[crop_id][1])


def model_status() -> dict:
    models_status = []
    for crop in SUPPORTED_CROPS:
        crop_id = crop["id"]
        path = _model_path(crop_id)
        metadata = _model_metadata(crop_id) if path.is_file() else {}
        models_status.append({
            "crop_id": crop_id,
            "crop_name": crop["name"],
            "available": path.is_file(),
            "model_version": _model_version(crop_id) if path.is_file() else None,
            "training_images": metadata.get("training_images"),
            "validation": {"accuracy": metadata.get("validation_accuracy"), "images": metadata.get("validation_images"), "design": metadata.get("validation_design")} if metadata else None,
        })
    potato = models_status[0]
    return {
        "available": any(item["available"] for item in models_status),
        "framework": "FastAI",
        "model_version": potato["model_version"],
        "supported_crops": [{**crop, "model_supported": models_status[index]["available"]} for index, crop in enumerate(SUPPORTED_CROPS)],
        "models": models_status,
        "limitation": "Plant Lens currently screens supported leaf categories for Irish potato and tomato; it does not provide a definitive diagnosis.",
        "source": MODEL_SOURCE,
        "validation": potato["validation"],
        "training_images": potato["training_images"],
    }


def _load_learner(crop_id: str = "irish-potato"):
    if crop_id in _learners:
        return _learners[crop_id]
    path = _model_path(crop_id)
    if not path.is_file():
        raise RuntimeError("No trained Plant Lens model is installed")
    with _learner_lock:
        if crop_id in _learners:
            return _learners[crop_id]
        try:
            from fastai.learner import load_learner
            _learners[crop_id] = load_learner(path, cpu=True)
            _learner_errors.pop(crop_id, None)
        except Exception as exc:
            _learner_errors[crop_id] = str(exc)
            raise RuntimeError("The configured FastAI model could not be loaded") from exc
    return _learners[crop_id]


def _normalize_label(label: str) -> str:
    text = re.sub(r"[_-]+", " ", str(label)).casefold()
    if "unsupported" in text or "not potato" in text:
        return "unsupported"
    if "early" in text and "blight" in text:
        return "early blight"
    if "late" in text and "blight" in text:
        return "late blight"
    if "bacterial" in text and "spot" in text:
        return "bacterial spot"
    if "leaf" in text and "mold" in text:
        return "leaf mold"
    if "septoria" in text:
        return "septoria leaf spot"
    if "spider" in text and "mite" in text:
        return "spider mites"
    if "target" in text and "spot" in text:
        return "target spot"
    if "mosaic" in text and "virus" in text:
        return "tomato mosaic virus"
    if "yellow" in text and "curl" in text and "virus" in text:
        return "tomato yellow leaf curl virus"
    if "healthy" in text:
        return "healthy"
    return text.strip()


def _validate_photo_quality(image_path: Path) -> dict:
    from PIL import Image, ImageStat, UnidentifiedImageError

    try:
        with Image.open(image_path) as image:
            image.load()
            width, height = image.size
            sample = image.convert("RGB").resize((64, 64))
            statistics = ImageStat.Stat(sample)
    except (OSError, UnidentifiedImageError) as exc:
        raise ImageQualityError("The uploaded file could not be read as a photograph") from exc
    if min(width, height) < 160:
        raise ImageQualityError("Move closer and retake the photo; it must be at least 160 pixels on each side")
    brightness = sum(statistics.mean) / 3
    contrast = sum(statistics.stddev) / 3
    if brightness < 25:
        raise ImageQualityError("The photo is too dark. Retake it in bright natural light")
    if brightness > 240:
        raise ImageQualityError("The photo is overexposed. Retake it without glare")
    if contrast < 8:
        raise ImageQualityError("The photo has too little visible detail. Focus on one leaf and retake it")
    return {"width": width, "height": height, "brightness": round(brightness, 1), "contrast": round(contrast, 1)}


def _predict_with_fastai(image_path: Path, crop_id: str = "irish-potato") -> list[dict]:
    learner = _load_learner(crop_id)
    _label, _index, probabilities = learner.predict(image_path)
    vocab = [str(item) for item in learner.dls.vocab]
    ranked = sorted(
        ({"label": _normalize_label(label), "confidence": round(float(probabilities[index]), 4)} for index, label in enumerate(vocab)),
        key=lambda item: item["confidence"], reverse=True,
    )
    return ranked


def _tomato_screening_decision(ranked: list[dict]) -> dict:
    """Return a conservative tomato screening decision.

    Four disease_dataset leaf-spot classes overlap heavily. We never expose their
    exact model label as a diagnosis; we only report the broader visual pattern
    when their combined probability clearly dominates all other categories.
    """
    top = ranked[0]
    if top["label"] in TOMATO_SPOT_LABELS:
        spot_score = sum(item["confidence"] for item in ranked if item["label"] in TOMATO_SPOT_LABELS)
        best_other = max(
            (item["confidence"] for item in ranked if item["label"] not in TOMATO_SPOT_LABELS),
            default=0.0,
        )
        accepted = spot_score >= 0.80 and spot_score - best_other >= 0.25
        return {
            "accepted": accepted,
            "reported_label": "tomato leaf spot pattern" if accepted else None,
            "reported_score": round(spot_score, 4),
            "minimum_confidence": 0.80,
            "minimum_margin": 0.25,
            "reason": "Several tomato leaf-spot diseases look alike. The model did not find a strong enough shared leaf-spot pattern." if not accepted else None,
        }

    second = ranked[1]["confidence"] if len(ranked) > 1 else 0.0
    minimum_confidence, minimum_margin = TOMATO_CLASS_THRESHOLDS.get(top["label"], (0.95, 0.40))
    accepted = top["confidence"] >= minimum_confidence and top["confidence"] - second >= minimum_margin
    return {
        "accepted": accepted,
        "reported_label": top["label"] if accepted else None,
        "reported_score": top["confidence"],
        "minimum_confidence": minimum_confidence,
        "minimum_margin": minimum_margin,
        "reason": "The tomato image did not meet the strict evidence level required to report this visual category." if not accepted else None,
    }


def _image_extension(content: bytes) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    raise HTTPException(status_code=422, detail="Upload a valid JPEG, PNG or WebP photograph")


def analyze_image(db: Session, owner_id: int, crop_id: str, original_filename: str, content: bytes) -> dict:
    if crop_id not in MODEL_CONFIG:
        raise HTTPException(status_code=422, detail="Plant Lens currently supports Irish potato and tomato")
    crop_name = CROP_NAMES[crop_id]
    max_bytes = settings.plant_lens_max_upload_mb * 1024 * 1024
    if len(content) < 512:
        raise HTTPException(status_code=422, detail="The image file is too small to analyze")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Image must be smaller than {settings.plant_lens_max_upload_mb} MB")
    extension = _image_extension(content)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_ROOT / f"{owner_id}_{uuid4().hex}{extension}"
    path.write_bytes(content)

    try:
        photo_quality = _validate_photo_quality(path)
        ranked = _predict_with_fastai(path, crop_id)
        top = ranked[0]
        margin = top["confidence"] - ranked[1]["confidence"] if len(ranked) > 1 else top["confidence"]
        minimum_confidence, minimum_margin = CROP_THRESHOLDS[crop_id]
        tomato_decision = _tomato_screening_decision(ranked) if crop_id == "tomato" else None
        uncertain = not tomato_decision["accepted"] if tomato_decision else top["confidence"] < minimum_confidence or margin < minimum_margin
        reported_score = tomato_decision["reported_score"] if tomato_decision else top["confidence"]
        if tomato_decision:
            minimum_confidence = tomato_decision["minimum_confidence"]
            minimum_margin = tomato_decision["minimum_margin"]
        common = {
            "confidence": reported_score,
            "alternatives": ranked[1:4],
            "model_version": _model_version(crop_id),
            "photo_quality": photo_quality,
            "decision_thresholds": {"minimum_confidence": minimum_confidence, "minimum_margin": minimum_margin},
            "evidence_level": "screening_only" if crop_id == "tomato" else "model_screening",
            "field_validation": "not_completed_for_rwanda" if crop_id == "tomato" else "limited",
            "sources": [MODEL_SOURCE, TRAINING_WORKFLOW_SOURCE] + ([SYMPTOM_SOURCE] if crop_id == "irish-potato" else []),
        }
        if uncertain:
            result = {
                **common,
                "analysis_status": "uncertain",
                "possible_condition": "Uncertain — take another photograph",
                "classification": None,
                "visible_symptoms": [],
                "recommended_inspection_steps": [
                    "Retake one sharp photo showing the full leaf in natural light",
                    "Photograph the other side of the same leaf",
                    "Submit a second affected leaf from another plant",
                ],
                "expert_confirmation_required": True,
                "uncertainty_reason": tomato_decision["reason"] if tomato_decision else "The model confidence or separation from the next class was too low to report a reliable category.",
                "disclaimer": "No condition is reported. It is safer to say uncertain than to guess from this photograph.",
            }
            review_status = "needs_better_photo"
        elif top["label"] == "unsupported":
            result = {
                **common,
                "analysis_status": "unsupported_image",
                "possible_condition": f"Not recognized as a supported {crop_name} leaf",
                "classification": "unsupported",
                "visible_symptoms": [],
                "recommended_inspection_steps": [
                    f"Photograph one {crop_name} leaf so it fills most of the frame",
                    "Avoid people, screens, documents and unrelated crops",
                    "Use the whole leaf and a plain background where possible",
                ],
                "expert_confirmation_required": False,
                "disclaimer": "Plant Lens rejected this image instead of forcing an early-blight, late-blight or healthy result.",
            }
            review_status = "rejected_unsupported"
        else:
            reported_label = tomato_decision["reported_label"] if tomato_decision else top["label"]
            details = CLASS_DETAILS[crop_id].get(reported_label, {
                "condition": f"Possible {reported_label} pattern", "visible_symptoms": [],
                "inspection_steps": ["Take additional photographs and request expert review"],
            })
            disease_candidate = top["label"] != "healthy"
            result = {
                **common,
                "analysis_status": "completed",
                "possible_condition": details["condition"],
                "classification": reported_label,
                "model_top_class": top["label"],
                "leading_candidate": top["label"] if crop_id == "tomato" else None,
                "leading_candidate_score": top["confidence"] if crop_id == "tomato" else None,
                "candidate_is_confirmed": False if crop_id == "tomato" else None,
                "visible_symptoms": details["visible_symptoms"],
                "recommended_inspection_steps": details["inspection_steps"],
                "expert_confirmation_required": disease_candidate,
                "disclaimer": "This visual screening match is not a definitive diagnosis or proof of disease. Similar symptoms can have different causes.",
            }
            review_status = "pending_expert" if disease_candidate else "ai_screened"
        confidence = reported_score
        model_version = _model_version(crop_id)
    except ImageQualityError as exc:
        confidence = None
        model_version = _model_version(crop_id) if _model_path(crop_id).is_file() else None
        review_status = "needs_better_photo"
        result = {
            "analysis_status": "invalid_image",
            "possible_condition": "Photo cannot be assessed",
            "classification": None,
            "confidence": None,
            "alternatives": [],
            "visible_symptoms": [],
            "recommended_inspection_steps": [str(exc)],
            "expert_confirmation_required": False,
            "model_version": model_version,
            "disclaimer": "No condition was reported because the photograph did not pass the quality check.",
            "sources": [MODEL_SOURCE, SYMPTOM_SOURCE],
        }
    except Exception as exc:
        confidence = None
        model_version = None
        review_status = "awaiting_model"
        result = {
            "analysis_status": "model_unavailable" if isinstance(exc, RuntimeError) else "analysis_failed",
            "possible_condition": None,
            "classification": None,
            "confidence": None,
            "alternatives": [],
            "visible_symptoms": [],
            "recommended_inspection_steps": [
                "Take a clear photograph of both sides of an affected leaf",
                "Photograph symptoms on several plants",
                "Ask a local agronomist or plant-health officer to inspect the crop",
            ],
            "expert_confirmation_required": True,
            "model_version": None,
            "model_message": str(exc) if isinstance(exc, RuntimeError) else "The image could not be processed by the configured model.",
            "disclaimer": "The photograph was saved, but no prediction was generated because a trained model is not installed.",
            "sources": [MODEL_SOURCE, SYMPTOM_SOURCE],
        }

    case = PlantLensCase(
        owner_id=owner_id, crop_id=crop_id, image_path=str(path),
        original_filename=Path(original_filename or "plant-photo").name[:255], prediction_json=json.dumps(result),
        model_version=model_version, confidence=confidence, review_status=review_status,
    )
    db.add(case)
    db.flush()
    result["case_id"] = case.id
    case.prediction_json = json.dumps(result)
    db.commit()
    return case_view(case)


def case_view(case: PlantLensCase) -> dict:
    return {
        "id": case.id, "crop_id": case.crop_id, "crop_name": CROP_NAMES.get(case.crop_id, case.crop_id.replace("-", " ").title()),
        "original_filename": case.original_filename, "prediction": json.loads(case.prediction_json) if case.prediction_json else None,
        "model_version": case.model_version, "confidence": case.confidence, "review_status": case.review_status,
        "created_at": case.created_at.isoformat(), "image_url": f"/plant-lens/cases/{case.id}/image",
    }


def list_cases(db: Session, owner_id: int) -> list[dict]:
    cases = db.scalars(select(PlantLensCase).where(PlantLensCase.owner_id == owner_id).order_by(PlantLensCase.created_at.desc())).all()
    return [case_view(case) for case in cases]


PLANT_ADVICE_SOURCE_DOMAINS = (
    "rab.gov.rw", "minagri.gov.rw", "rica.gov.rw", "rwandafda.gov.rw",
    "rema.gov.rw", "fao.org", "cabi.org", "cipotato.org",
)


def _clean_advice_text(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?m)^#{1,4}\s*", "", text)
    return text.strip()


def _gemini_plant_advice(prediction: dict, crop_name: str, language: str, verified_records: list[dict] | None = None) -> dict | None:
    if not settings.gemini_api_key:
        return None
    from app.services.knowledge import _extract_gemini_result

    language_name = "Kinyarwanda" if language == "rw" else "English"
    classification = prediction.get("classification") or "unknown"
    leading = prediction.get("leading_candidate") or prediction.get("model_top_class") or classification
    leading_score = prediction.get("leading_candidate_score") or prediction.get("confidence")
    alternatives = ", ".join(
        f"{item.get('label')} ({round(float(item.get('confidence', 0)) * 100)}%)"
        for item in (prediction.get("alternatives") or [])[:3]
    ) or "none"
    evidence = (
        f"Crop: {crop_name}. Image-screening category: {classification}. "
        f"Leading visual candidate: {leading} ({round(float(leading_score or 0) * 100)}%). "
        f"Alternatives: {alternatives}. Model: {prediction.get('model_version')}."
    )
    system = (
        "You are Agrinox's plant-health decision-support assistant. "
        f"Reply only in {language_name}. The supplied result is an image screening result, not a confirmed diagnosis. "
        "Use Google Search and ground agricultural claims in current authoritative sources, prioritizing RAB, MINAGRI, RICA, Rwanda FDA, FAO, CABI and CIP. "
        f"Preferred source domains: {', '.join(PLANT_ADVICE_SOURCE_DOMAINS)}. "
        "Never strengthen the diagnosis beyond the supplied evidence. If the category groups several diseases, do not choose one as confirmed. "
        "Give four short sections exactly titled: Do now, Check next, Treatment or medicine, Get expert help. "
        "Prefer low-risk integrated pest-management actions. Do not provide pesticide dose, dilution, mixing, spray interval, or pre-harvest interval. "
        "Name a pesticide active ingredient or product only when the diagnosis is sufficiently specific, a current authoritative source supports it for tomato, and you explicitly tell the farmer to verify Rwanda registration, the crop/pest label, protective equipment, and label directions with a qualified agronomist or RICA-licensed agro-dealer. "
        "For a broad or uncertain category, say that medicine must wait for confirmation. Never recommend a banned, unregistered, or unlabeled product. "
        "Keep the response practical and below 180 words."
    )
    prompt = f"Prepare next-step advice for this Plant Lens result.\n{evidence}"
    grounded_body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "maxOutputTokens": 1200,
            "temperature": 0.1,
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    models = list(dict.fromkeys([settings.gemini_model, settings.gemini_fallback_model]))
    for model in models:
        try:
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
                json=grounded_body,
                timeout=45,
            )
            response.raise_for_status()
            text, sources = _extract_gemini_result(response.json())
            if text:
                return {
                    "status": "ready",
                    "text": _clean_advice_text(text),
                    "sources": sources,
                    "model": model,
                    "response_mode": "gemini_grounded_web",
                    "language": language,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "safety_notice": "Do not buy or apply a pesticide from an image result alone. Confirm the problem and follow a currently registered Rwanda product label.",
                }
        except (httpx.HTTPError, ValueError):
            continue

    # If search grounding is temporarily unavailable, Gemini may still organize
    # non-chemical, low-risk actions. Chemical/product guidance is forbidden in
    # this fallback because it has no current supporting source.
    verified_records = verified_records or []
    local_context = "\n\n".join(
        f"[{index}] {record['title']}\n{record['content']}\nSource: {record['source_url']}"
        for index, record in enumerate(verified_records, 1)
    )
    fallback_prompt = prompt + (f"\n\nVerified Rwanda records:\n{local_context}" if local_context else "")
    fallback_body = {
        "systemInstruction": {"parts": [{"text": system + " Google Search is unavailable. Use only the supplied verified Rwanda records for factual guidance. Do not name any pesticide, active ingredient, product, or dose. Give only inspection, isolation, sanitation, monitoring, and expert-confirmation steps. Cite supplied records as [1], [2]."}]},
        "contents": [{"role": "user", "parts": [{"text": fallback_prompt}]}],
        "generationConfig": {"maxOutputTokens": 900, "temperature": 0.1, "thinkingConfig": {"thinkingLevel": "low"}},
    }
    for model in reversed(models):
        try:
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
                json=fallback_body,
                timeout=35,
            )
            response.raise_for_status()
            text, _sources = _extract_gemini_result(response.json())
            if text:
                return {
                    "status": "ready" if verified_records else "limited",
                    "text": _clean_advice_text(text),
                    "sources": [{"article_id": record.get("article_id"), "article_title": record["title"], "source_url": record["source_url"], "score": 1.0} for record in verified_records],
                    "model": model,
                    "response_mode": "gemini_verified_retrieval" if verified_records else "gemini_nonchemical_fallback",
                    "language": language,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "safety_notice": "Google Search grounding was unavailable. Gemini used verified Rwanda records and intentionally excluded unverified pesticide or medicine recommendations." if verified_records else "Source-grounded treatment guidance was unavailable. This response intentionally excludes pesticide and medicine recommendations.",
                }
        except (httpx.HTTPError, ValueError):
            continue
    return None


def generate_case_advice(db: Session, owner_id: int, case_id: int, language: str = "en") -> dict:
    case = db.scalar(select(PlantLensCase).where(PlantLensCase.id == case_id, PlantLensCase.owner_id == owner_id))
    if not case:
        raise HTTPException(status_code=404, detail="Plant Lens case not found")
    prediction = json.loads(case.prediction_json) if case.prediction_json else {}
    if prediction.get("analysis_status") != "completed" or prediction.get("classification") in (None, "healthy", "unsupported"):
        raise HTTPException(status_code=409, detail="Gemini advice is available only after a supported plant problem is detected")
    cache_key = f"advice-v2:{prediction.get('model_version')}:{prediction.get('classification')}:{prediction.get('leading_candidate')}:{language}"
    cached = prediction.get("gemini_advice")
    if isinstance(cached, dict) and cached.get("cache_key") == cache_key:
        return cached
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Gemini advice is not configured")
    from sqlalchemy.orm import selectinload
    from app.db.models import KnowledgeArticle
    from app.services.knowledge import seed_knowledge

    seed_knowledge(db)
    articles = db.scalars(
        select(KnowledgeArticle).options(selectinload(KnowledgeArticle.sources)).where(
            KnowledgeArticle.slug.in_(("verified-crop-disease-information", "integrated-pest-management-rwanda"))
        )
    ).all()
    verified_records = []
    for article in articles:
        content = article.content_rw if language == "rw" else article.content_en
        title = article.title_rw if language == "rw" else article.title_en
        for source in article.sources:
            verified_records.append({"article_id": article.id, "title": title, "content": content, "source_url": source.url})
    advice = _gemini_plant_advice(prediction, CROP_NAMES.get(case.crop_id, case.crop_id), language, verified_records)
    if not advice:
        raise HTTPException(status_code=502, detail="Gemini could not generate safe advice right now. The image result remains available; try advice again later")
    advice["cache_key"] = cache_key
    prediction["gemini_advice"] = advice
    case.prediction_json = json.dumps(prediction)
    db.add(case)
    db.commit()
    return advice
