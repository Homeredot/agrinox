from __future__ import annotations

import calendar as month_calendar
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.services.notifications import configured as email_configured, send_due_calendar_reminders as send_central_calendar_reminders
from app.db.models import CalendarTask, FarmField, User


RWANDA_TZ = timezone(timedelta(hours=2))
MINAGRI_CALENDAR_URL = "https://www.minagri.gov.rw/fileadmin/user_upload/Minagri/Publications/Policies_and_strategies/Nutrition_Sensitive_Agriculture_Mainstreaming_Guideline_FINAL.pdf"
RAB_EXTENSION_URL = "https://www.rab.gov.rw/1-1/news-details/rab-through-twigire-muhinzi-trains-14000-farmer-promoters-on-agricultural-practices"

CROP_DURATIONS = {
    "beans": 85,
    "maize": 120,
    "irish potatoes": 110,
    "irish potato": 110,
    "potato": 110,
    "rice": 120,
    "tomato": 100,
    "tomatoes": 100,
    "wheat": 120,
}

CATEGORIES = {
    "soil_preparation": "Soil preparation",
    "planting": "Planting",
    "fertilizer_assessment": "Fertilizer assessment",
    "irrigation": "Irrigation",
    "pest_scouting": "Pest scouting",
    "field_maintenance": "Field maintenance",
    "harvesting": "Harvesting",
    "post_harvest": "Post-harvest storage",
}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def task_view(task: CalendarTask) -> dict:
    field = task.field
    farm = field.farm if field else None
    return {
        "id": task.id,
        "field_id": task.field_id,
        "crop_plan_id": task.crop_plan_id,
        "field_name": field.name if field else "Removed field",
        "farm_id": farm.id if farm else None,
        "farm_name": farm.name if farm else "Removed farm",
        "title": task.title,
        "description": task.description,
        "category": task.category,
        "category_label": CATEGORIES.get(task.category, task.category.replace("_", " ").title()),
        "crop": task.crop,
        "growth_stage": task.growth_stage,
        "due_at": task.due_at.isoformat(),
        "reminder_at": task.reminder_at.isoformat() if task.reminder_at else None,
        "recurrence": task.recurrence,
        "recurrence_interval": task.recurrence_interval,
        "status": task.status,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "reminder_dismissed": task.reminder_dismissed,
        "email_reminder": task.email_reminder,
        "email_sent_at": task.email_sent_at.isoformat() if task.email_sent_at else None,
        "source_type": task.source_type,
        "source_title": task.source_title,
        "source_url": task.source_url,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def task_query(owner_id: int):
    return (
        select(CalendarTask)
        .where(CalendarTask.owner_id == owner_id)
        .options(selectinload(CalendarTask.field).selectinload(FarmField.farm))
    )


def get_task(db: Session, owner_id: int, task_id: int) -> CalendarTask | None:
    return db.scalar(task_query(owner_id).where(CalendarTask.id == task_id))


def list_tasks(
    db: Session,
    owner_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    field_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    statement = task_query(owner_id)
    if date_from is not None:
        statement = statement.where(CalendarTask.due_at >= date_from)
    if date_to is not None:
        statement = statement.where(CalendarTask.due_at <= date_to)
    if field_id is not None:
        statement = statement.where(CalendarTask.field_id == field_id)
    if status is not None:
        statement = statement.where(CalendarTask.status == status)
    tasks = db.scalars(statement.order_by(CalendarTask.due_at, CalendarTask.id)).all()
    return [task_view(task) for task in tasks]


def overview(db: Session, owner_id: int) -> dict:
    now = datetime.now(timezone.utc)
    today = now.astimezone(RWANDA_TZ).date()
    tasks = db.scalars(task_query(owner_id).order_by(CalendarTask.due_at)).all()
    due_today = 0
    overdue = 0
    upcoming = 0
    completed_this_month = 0
    for task in tasks:
        due_date = _aware(task.due_at).astimezone(RWANDA_TZ).date()
        if task.status == "pending":
            if due_date == today:
                due_today += 1
            if due_date < today:
                overdue += 1
            if today <= due_date <= today + timedelta(days=7):
                upcoming += 1
        elif task.completed_at:
            completed = _aware(task.completed_at).astimezone(RWANDA_TZ).date()
            if completed.year == today.year and completed.month == today.month:
                completed_this_month += 1
    return {
        "due_today": due_today,
        "overdue": overdue,
        "upcoming_7_days": upcoming,
        "completed_this_month": completed_this_month,
        "total_tasks": len(tasks),
        "email_notifications": {
            "configured": email_configured(),
            "message": "Email delivery is active." if email_configured() else "Email delivery is currently unavailable; in-app reminders remain active.",
        },
    }


def reminders(db: Session, owner_id: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    tasks = db.scalars(
        task_query(owner_id).where(
            CalendarTask.status == "pending",
            CalendarTask.reminder_at.is_not(None),
            CalendarTask.reminder_at <= now,
            CalendarTask.reminder_dismissed.is_(False),
        ).order_by(CalendarTask.reminder_at)
    ).all()
    return [task_view(task) for task in tasks]


def next_due_at(due_at: datetime, recurrence: str, interval: int) -> datetime:
    if recurrence == "daily":
        return due_at + timedelta(days=interval)
    if recurrence == "weekly":
        return due_at + timedelta(weeks=interval)
    if recurrence == "monthly":
        month_index = due_at.month - 1 + interval
        year = due_at.year + month_index // 12
        month = month_index % 12 + 1
        day = min(due_at.day, month_calendar.monthrange(year, month)[1])
        return due_at.replace(year=year, month=month, day=day)
    return due_at


def complete_task(db: Session, task: CalendarTask) -> CalendarTask | None:
    now = datetime.now(timezone.utc)
    task.status = "completed"
    task.completed_at = now
    next_task = None
    if task.recurrence != "none":
        following_due = next_due_at(task.due_at, task.recurrence, task.recurrence_interval)
        reminder_delta = task.due_at - task.reminder_at if task.reminder_at else None
        next_task = CalendarTask(
            owner_id=task.owner_id,
            field_id=task.field_id,
            crop_plan_id=task.crop_plan_id,
            title=task.title,
            description=task.description,
            category=task.category,
            crop=task.crop,
            growth_stage=task.growth_stage,
            due_at=following_due,
            reminder_at=following_due - reminder_delta if reminder_delta else None,
            recurrence=task.recurrence,
            recurrence_interval=task.recurrence_interval,
            email_reminder=task.email_reminder,
            source_type=task.source_type,
            source_title=task.source_title,
            source_url=task.source_url,
        )
        db.add(next_task)
    return next_task


def suggestions(crop: str, planting_date: date, growth_stage: str | None = None) -> list[dict]:
    crop_name = crop.strip().title()
    duration = CROP_DURATIONS.get(crop.strip().casefold(), 105)
    base = datetime.combine(planting_date, datetime.min.time().replace(hour=8), RWANDA_TZ)
    harvest = base + timedelta(days=duration)
    stage = (growth_stage or "").strip().casefold()
    templates = [
        ("soil_preparation", "Prepare soil and drainage", -14, "pre-planting", "Clear the field, inspect drainage and prepare soil before planting."),
        ("planting", f"Plant {crop_name}", 0, "planting", "Confirm current seasonal weather guidance and locally suitable seed before planting."),
        ("irrigation", "Check crop establishment and soil moisture", 3, "establishment", "Inspect emergence and soil moisture. Irrigate only when field evidence shows it is needed."),
        ("fertilizer_assessment", "Assess soil and fertilizer need", 14, "vegetative", "Review soil evidence and crop condition. Confirm product and rate with RwaSIS or an agronomist."),
        ("pest_scouting", "Scout for pests and disease symptoms", 14, "vegetative", "Walk the field systematically and record symptoms before choosing any treatment."),
        ("field_maintenance", "Weed and maintain the field", 21, "vegetative", "Check weeds, drainage, stakes or earthing-up needs appropriate to this crop."),
        ("harvesting", "Prepare for harvest", duration - 7, "maturity", "Check crop maturity, weather and labor before confirming the harvest date."),
        ("post_harvest", "Sort and store the harvest safely", duration, "post-harvest", "Clean, sort and store produce using crop-appropriate ventilation and handling."),
    ]
    result = []
    for category, title, offset, task_stage, description in templates:
        if stage and stage in {"harvest", "maturity", "post-harvest"} and task_stage in {"pre-planting", "planting", "establishment"}:
            continue
        due = base + timedelta(days=offset) if category not in {"harvesting", "post_harvest"} else (harvest - timedelta(days=7) if category == "harvesting" else harvest)
        result.append({
            "title": title,
            "description": description,
            "category": category,
            "crop": crop_name,
            "growth_stage": task_stage,
            "due_at": due.isoformat(),
            "reminder_at": (due - timedelta(days=1)).isoformat(),
            "recurrence": "weekly" if category == "pest_scouting" else "none",
            "recurrence_interval": 1,
            "source_type": "suggested",
            "source_title": "Rwanda seasonal calendar and RAB extension workflow",
            "source_url": MINAGRI_CALENDAR_URL if category in {"soil_preparation", "planting", "harvesting"} else RAB_EXTENSION_URL,
            "evidence_note": "Planning estimate based on planting date and crop stage; confirm timing with current weather and a local agronomist.",
            "confidence": "planning guidance",
        })
    return result


def send_due_email_reminders(db: Session, user: User) -> dict:
    return send_central_calendar_reminders(db, user)
