from __future__ import annotations

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AppNotification, CalendarTask, EmailDelivery, NotificationPreference, User


CATEGORY_FIELDS = {
    "calendar_reminders": "calendar_reminders",
    "irrigation_events": "irrigation_events",
    "device_alerts": "device_alerts",
    "soil_alerts": "soil_alerts",
    "plant_results": "plant_results",
    "planning_updates": "planning_updates",
    "finance_updates": "finance_updates",
    "security_updates": "security_updates",
}


def configured() -> bool:
    return bool(settings.email_enabled and settings.email_host and settings.email_user and settings.email_pass)


def get_preferences(db: Session, user_id: int) -> NotificationPreference:
    preferences = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    if not preferences:
        preferences = NotificationPreference(user_id=user_id)
        db.add(preferences)
        db.flush()
    return preferences


def preference_view(preferences: NotificationPreference) -> dict:
    return {
        "enabled": preferences.enabled,
        **{field: getattr(preferences, field) for field in CATEGORY_FIELDS.values()},
        "email_configured": configured(),
        "updated_at": preferences.updated_at.isoformat() if preferences.updated_at else None,
    }


def delivery_view(delivery: EmailDelivery) -> dict:
    return {
        "id": delivery.id,
        "category": delivery.category,
        "subject": delivery.subject,
        "status": delivery.status,
        "error_message": delivery.error_message,
        "created_at": delivery.created_at.isoformat(),
        "sent_at": delivery.sent_at.isoformat() if delivery.sent_at else None,
    }


def notification_view(notification: AppNotification) -> dict:
    return {
        "id": notification.id,
        "category": notification.category,
        "title": notification.title,
        "message": notification.message,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
    }


def _send_smtp(recipient: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.email_from or settings.email_user
    message["To"] = recipient
    message.set_content(body)
    message.add_alternative(
        "<div style='font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#203126'>"
        "<div style='padding:18px 22px;background:#244b34;color:white;border-radius:14px 14px 0 0'>"
        "<strong style='font-size:20px'>Agrinox</strong></div>"
        f"<div style='padding:24px;border:1px solid #d9e4da;border-top:0;border-radius:0 0 14px 14px;white-space:pre-line'>{escape(body)}</div>"
        "</div>",
        subtype="html",
    )
    with smtplib.SMTP(settings.email_host, settings.email_port, timeout=12) as smtp:
        if settings.email_use_tls:
            smtp.starttls()
        smtp.login(settings.email_user, settings.email_pass.replace(" ", ""))
        smtp.send_message(message)


def send_notification(
    db: Session,
    user: User,
    *,
    category: str,
    event_key: str,
    subject_en: str,
    body_en: str,
    subject_rw: str | None = None,
    body_rw: str | None = None,
    force: bool = False,
    store_in_app: bool = True,
) -> dict:
    if category not in CATEGORY_FIELDS:
        raise ValueError(f"Unsupported email category: {category}")
    language = "rw" if user.preferred_language == "rw" else "en"
    subject = subject_rw if language == "rw" and subject_rw else subject_en
    body = body_rw if language == "rw" and body_rw else body_en

    if store_in_app:
        in_app = db.scalar(select(AppNotification).where(AppNotification.user_id == user.id, AppNotification.event_key == event_key))
        if not in_app:
            db.add(AppNotification(user_id=user.id, category=category, event_key=event_key, title=subject, message=body))
            db.commit()

    if not configured():
        return {"status": "not_configured", "sent": False}
    preferences = get_preferences(db, user.id)
    if not force and (not preferences.enabled or not getattr(preferences, CATEGORY_FIELDS[category])):
        return {"status": "disabled_by_user", "sent": False}

    existing_delivery = db.scalar(select(EmailDelivery).where(EmailDelivery.event_key == event_key))
    if existing_delivery and existing_delivery.status == "sent":
        return {"status": "already_sent", "sent": False}

    delivery = existing_delivery or EmailDelivery(user_id=user.id, category=category, event_key=event_key, subject=subject, status="pending")
    delivery.subject = subject
    delivery.status = "pending"
    delivery.error_message = None
    db.add(delivery)
    db.commit()
    try:
        _send_smtp(user.email, subject, body)
    except (OSError, smtplib.SMTPException) as exc:
        delivery.status = "failed"
        delivery.error_message = str(exc)[:500]
        db.add(delivery)
        db.commit()
        return {"status": "failed", "sent": False}
    delivery.status = "sent"
    delivery.sent_at = datetime.now(timezone.utc)
    db.add(delivery)
    db.commit()
    return {"status": "sent", "sent": True}


def send_due_calendar_reminders(db: Session, user: User) -> dict:
    if not configured():
        return {"configured": False, "sent": 0, "message": "Email is not configured; in-application reminders remain active."}
    due = db.scalars(
        select(CalendarTask).where(
            CalendarTask.owner_id == user.id,
            CalendarTask.status == "pending",
            CalendarTask.email_sent_at.is_(None),
            CalendarTask.reminder_at.is_not(None),
            CalendarTask.reminder_at <= datetime.now(timezone.utc),
        )
    ).all()
    sent = 0
    for task in due:
        result = send_notification(
            db,
            user,
            category="calendar_reminders",
            event_key=f"calendar-reminder:{task.id}:{task.reminder_at.isoformat() if task.reminder_at else 'due'}",
            subject_en=f"Farm task reminder: {task.title}",
            body_en=f"Hello {user.full_name},\n\nTask: {task.title}\nDue: {task.due_at.isoformat()}\nField: {task.field.name}\n\n{task.description or ''}\n\nOpen Agrinox to update this task.",
            subject_rw=f"Urwibutso rw'umurimo: {task.title}",
            body_rw=f"Muraho {user.full_name},\n\nUmurimo: {task.title}\nIgihe ntarengwa: {task.due_at.isoformat()}\nIgice cy'umurima: {task.field.name}\n\n{task.description or ''}\n\nFungura Agrinox uvugurure uyu murimo.",
        )
        if result["sent"]:
            task.email_sent_at = datetime.now(timezone.utc)
            db.add(task)
            db.commit()
            sent += 1
    return {"configured": True, "sent": sent, "message": f"Sent {sent} reminder email(s)."}


def recent_deliveries(db: Session, user_id: int, limit: int = 20) -> list[dict]:
    items = db.scalars(select(EmailDelivery).where(EmailDelivery.user_id == user_id).order_by(EmailDelivery.created_at.desc()).limit(limit)).all()
    return [delivery_view(item) for item in items]


def recent_notifications(db: Session, user_id: int, limit: int = 30, unread_only: bool = False) -> list[dict]:
    query = select(AppNotification).where(AppNotification.user_id == user_id)
    if unread_only:
        query = query.where(AppNotification.is_read.is_(False))
    items = db.scalars(query.order_by(AppNotification.created_at.desc()).limit(limit)).all()
    return [notification_view(item) for item in items]


def unread_notification_count(db: Session, user_id: int) -> int:
    return int(db.scalar(select(func.count(AppNotification.id)).where(AppNotification.user_id == user_id, AppNotification.is_read.is_(False))) or 0)


def mark_notification_read(db: Session, user_id: int, notification_id: int) -> dict | None:
    item = db.scalar(select(AppNotification).where(AppNotification.id == notification_id, AppNotification.user_id == user_id))
    if not item:
        return None
    if not item.is_read:
        item.is_read = True
        item.read_at = datetime.now(timezone.utc)
        db.add(item)
        db.commit()
        db.refresh(item)
    return notification_view(item)


def mark_all_notifications_read(db: Session, user_id: int) -> int:
    result = db.execute(
        update(AppNotification)
        .where(AppNotification.user_id == user_id, AppNotification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return int(result.rowcount or 0)
