import json
import smtplib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import AuditLog, CalendarTask, Cell, CropPlan, Device, District, Farm, FarmField, FinancialPlan, FinancialTransaction, IrrigationCommand, KnowledgeArticle, KnowledgeConversation, KnowledgeMessage, NotificationPreference, PlantLensCase, Province, SatelliteArea, Sensor, SensorReading, Sector, SoilContext, SoilReading, TwoFactorChallenge, User, Village, WaterSource
from app.db.session import get_db
from app.dependencies import current_user
from app.schemas import CalendarSuggestionRequest, CalendarTaskCreate, CalendarTaskUpdate, CropPlanCreate, CropRecommendationRequest, DeviceCommandStatus, DeviceCreate, DeviceUpdate, FarmCreate, FarmOut, FieldCreate, FieldOut, FinancialCalculationRequest, FinancialPlanCreate, FinancialPlanUpdate, FinancialTransactionCreate, FirmwareInstallRequest, IoTHeartbeat, IoTReadingBatch, IrrigationCommandCreate, IrrigationConfigUpdate, KnowledgeQuestion, LanguageUpdate, LoginRequest, NotificationPreferenceUpdate, PasswordChange, PlantLensReviewUpdate, ProfileUpdate, SatelliteAreaCreate, SatelliteMonitorRequest, SoilContextUpdate, SoilReadingCreate, TokenOut, TwoFactorCodeRequest, TwoFactorSetupRequest, UserCreate, UserOut, WaterSourceCreate, WaterSourceUpdate
from app.services.calendar import complete_task, get_task as get_calendar_task, list_tasks as list_calendar_tasks, overview as calendar_overview, reminders as calendar_reminders, send_due_email_reminders, suggestions as calendar_suggestions, task_view as calendar_task_view
from app.services.crop_planning import list_plans, planning_options, recommend_crops, save_plan
from app.services.devices import configure_firmware, exchange, flash_firmware, local_device_api_url, scan_usb_ports
from app.services.finance import calculate as calculate_financials, crop_plan_options as finance_crop_plan_options, get_plan as get_financial_plan, list_plans as list_financial_plans, plan_view as financial_plan_view, transaction_view as financial_transaction_view
from app.services.geocoding import cell_map_focus, reverse_geocode, search_locations
from app.services.geometry import manual_area, polygon_area_m2
from app.services.irrigation import COMMAND_TTL_MINUTES, authenticate_device, command_view, config_view, create_command, get_or_create_config, ingest_readings, irrigation_status, pending_device_commands, provision_device_key
from app.services.locations import options, validate_hierarchy
from app.services.plant_lens import UPLOAD_ROOT, analyze_image, case_view, generate_case_advice, list_cases, model_status
from app.services.knowledge import answer_question, article_view, conversation_view, seed_knowledge
from app.services.soil import soil_dashboard
from app.services.weather import weather_dashboard
from app.services.satellite import circle_geometry, integration_status, ndvi_image, satellite_dashboard
from app.services.district_intelligence import boundaries as district_boundaries, csv_export as district_csv_export, dashboard as district_dashboard, options as district_options, pdf_export as district_pdf_export
from app.services.notifications import get_preferences, mark_all_notifications_read, mark_notification_read, preference_view, recent_deliveries, recent_notifications, send_notification, unread_notification_count
from app.services.two_factor import create_challenge, encrypt_secret, masked_email, new_totp_secret, provisioning_uri, qr_data_url, status_view as two_factor_status_view, verify_challenge
from app.services.water_sources import compatible_sensors, list_sources, set_primary, source_view, validate_sensor
from app.services.profile import delete_profile_image, profile_image_file, save_profile_image

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health():
    return {"status": "ok", "module": "yield-management"}


def _send_welcome_email(db: Session, user: User) -> None:
    send_notification(
        db, user, category="security_updates", event_key=f"welcome:{user.id}",
        subject_en="Welcome to Agrinox",
        body_en=f"Hello {user.full_name},\n\nYour Agrinox account is ready. Register your farm and fields before connecting devices or using agricultural intelligence.\n\nYou can control email categories at any time in Notification settings.",
        subject_rw="Murakaza neza kuri Agrinox",
        body_rw=f"Muraho {user.full_name},\n\nKonti yawe ya Agrinox iriteguye. Banza wandike umurima n'ibice byawo mbere yo guhuza ibikoresho cyangwa gukoresha amakuru y'ubuhinzi.\n\nUshobora guhindura imeyili ushaka kwakira muri Igenamiterere ry'amatangazo.",
    )


@router.post("/auth/register", status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        preferred_language=payload.preferred_language,
        is_active=not settings.email_verification_required,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    get_preferences(db, user.id)
    db.commit()
    if settings.email_verification_required:
        token, _, delivery = create_challenge(db, user, purpose="registration", method="email")
        if not delivery or not delivery.get("sent"):
            db.delete(user)
            db.commit()
            raise HTTPException(status_code=503, detail="The confirmation email could not be sent. Check email delivery and try again")
        return {
            "email_verification_required": True,
            "challenge_token": token,
            "method": "email",
            "masked_email": masked_email(user.email),
            "expires_in_minutes": 10,
        }
    _send_welcome_email(db, user)
    return TokenOut(access_token=create_access_token(user.id), user=user)


@router.post("/auth/register/verify", response_model=TokenOut)
def verify_registration_email(payload: TwoFactorCodeRequest, db: Session = Depends(get_db)):
    challenge, _ = verify_challenge(db, payload.challenge_token, payload.code, "registration")
    user = db.get(User, challenge.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="This account confirmation is no longer valid")
    if user.is_active:
        raise HTTPException(status_code=409, detail="This email address is already confirmed")
    user.is_active = True
    db.commit()
    db.refresh(user)
    _send_welcome_email(db, user)
    return TokenOut(access_token=create_access_token(user.id), user=user)


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Confirm your email address before signing in")
    if user.two_factor_method in {"email", "authenticator"}:
        token, _, delivery = create_challenge(db, user, purpose="login", method=user.two_factor_method)
        if user.two_factor_method == "email" and (not delivery or not delivery.get("sent")):
            raise HTTPException(status_code=503, detail="The email verification code could not be sent. Try again shortly")
        return {
            "two_factor_required": True,
            "challenge_token": token,
            "method": user.two_factor_method,
            "masked_email": masked_email(user.email) if user.two_factor_method == "email" else None,
            "expires_in_minutes": 10,
        }
    return TokenOut(access_token=create_access_token(user.id), user=user)


@router.post("/auth/2fa/login/verify", response_model=TokenOut)
def verify_two_factor_login(payload: TwoFactorCodeRequest, db: Session = Depends(get_db)):
    challenge, _ = verify_challenge(db, payload.challenge_token, payload.code, "login")
    user = db.get(User, challenge.user_id)
    if not user or not user.is_active or user.two_factor_method != challenge.method:
        raise HTTPException(status_code=401, detail="Two-step verification is no longer active for this account")
    return TokenOut(access_token=create_access_token(user.id), user=user)


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/auth/me", response_model=UserOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    changes = payload.model_dump(exclude_unset=True)
    if "email" in changes:
        email = str(changes["email"]).strip().lower()
        existing = db.scalar(select(User).where(User.email == email, User.id != user.id))
        if existing:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        user.email = email
    if "full_name" in changes:
        user.full_name = str(changes["full_name"]).strip()
    for field in ("phone", "location", "bio"):
        if field in changes:
            value = changes[field]
            setattr(user, field, str(value).strip() if value else None)
    if "avatar_key" in changes or "avatar_color" in changes:
        delete_profile_image(user.profile_image_path)
        user.profile_image_path = None
        user.avatar_kind = "vector"
        if "avatar_key" in changes:
            user.avatar_key = changes["avatar_key"]
        if "avatar_color" in changes:
            user.avatar_color = changes["avatar_color"]
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/me/avatar", response_model=UserOut)
async def upload_profile_avatar(image: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    content = await image.read()
    new_path = save_profile_image(user.id, content, image.content_type)
    old_path = user.profile_image_path
    user.profile_image_path = new_path
    user.avatar_kind = "photo"
    db.commit()
    db.refresh(user)
    delete_profile_image(old_path)
    return user


@router.get("/auth/me/avatar")
def get_profile_avatar(user: User = Depends(current_user)):
    return FileResponse(profile_image_file(user.profile_image_path), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.delete("/auth/me/avatar", response_model=UserOut)
def remove_profile_avatar(db: Session = Depends(get_db), user: User = Depends(current_user)):
    old_path = user.profile_image_path
    user.profile_image_path = None
    user.avatar_kind = "vector"
    db.commit()
    db.refresh(user)
    delete_profile_image(old_path)
    return user


@router.post("/auth/me/password")
def change_password(payload: PasswordChange, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different")
    user.password_hash = hash_password(payload.new_password)
    now = datetime.now(timezone.utc)
    for challenge in db.scalars(select(TwoFactorChallenge).where(
        TwoFactorChallenge.user_id == user.id,
        TwoFactorChallenge.consumed_at.is_(None),
    )):
        challenge.consumed_at = now
    db.commit()
    result = send_notification(
        db, user, category="security_updates", event_key=f"password-changed:{user.id}:{datetime.now(timezone.utc).isoformat()}",
        subject_en="Your Agrinox password was changed",
        body_en="Your Agrinox password was changed. If you did not make this change, contact support immediately.",
        subject_rw="Ijambo ry'ibanga rya Agrinox ryahinduwe",
        body_rw="Ijambo ry'ibanga rya Agrinox ryahinduwe. Niba atari wowe wabikoze, hamagara ubufasha ako kanya.",
    )
    return {"changed": True, "notification_status": result["status"]}


@router.get("/auth/2fa/status")
def two_factor_status(user: User = Depends(current_user)):
    return two_factor_status_view(user)


@router.post("/auth/2fa/setup/email")
def setup_email_two_factor(payload: TwoFactorSetupRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    token, _, delivery = create_challenge(db, user, purpose="setup", method="email")
    if not delivery or not delivery.get("sent"):
        raise HTTPException(status_code=503, detail="The email verification code could not be sent. Check email configuration and try again")
    return {"challenge_token": token, "method": "email", "masked_email": masked_email(user.email), "expires_in_minutes": 10}


@router.post("/auth/2fa/setup/authenticator")
def setup_authenticator_two_factor(payload: TwoFactorSetupRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    secret = new_totp_secret()
    uri = provisioning_uri(secret, user.email)
    token, _, _ = create_challenge(db, user, purpose="setup", method="authenticator", pending_secret=secret)
    return {"challenge_token": token, "method": "authenticator", "secret": secret, "otpauth_uri": uri, "qr_code_data_url": qr_data_url(uri), "expires_in_minutes": 10}


@router.post("/auth/2fa/setup/confirm")
def confirm_two_factor_setup(payload: TwoFactorCodeRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    challenge, secret = verify_challenge(db, payload.challenge_token, payload.code, "setup")
    if challenge.user_id != user.id:
        raise HTTPException(status_code=403, detail="This verification request belongs to another account")
    user.two_factor_method = challenge.method
    user.totp_secret_encrypted = encrypt_secret(secret) if challenge.method == "authenticator" and secret else None
    user.two_factor_enabled_at = datetime.now(timezone.utc)
    db.commit()
    return two_factor_status_view(user)


@router.post("/auth/2fa/disable/start")
def start_two_factor_disable(payload: TwoFactorSetupRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not user.two_factor_method:
        raise HTTPException(status_code=400, detail="Two-step verification is not enabled")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    token, _, delivery = create_challenge(db, user, purpose="disable", method=user.two_factor_method)
    if user.two_factor_method == "email" and (not delivery or not delivery.get("sent")):
        raise HTTPException(status_code=503, detail="The email verification code could not be sent. Try again shortly")
    return {"challenge_token": token, "method": user.two_factor_method, "masked_email": masked_email(user.email) if user.two_factor_method == "email" else None, "expires_in_minutes": 10}


@router.post("/auth/2fa/disable/confirm")
def confirm_two_factor_disable(payload: TwoFactorCodeRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    challenge, _ = verify_challenge(db, payload.challenge_token, payload.code, "disable")
    if challenge.user_id != user.id:
        raise HTTPException(status_code=403, detail="This verification request belongs to another account")
    user.two_factor_method = None
    user.totp_secret_encrypted = None
    user.two_factor_enabled_at = None
    db.commit()
    return two_factor_status_view(user)


@router.patch("/auth/me/language", response_model=UserOut)
def update_language(payload: LanguageUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    user.preferred_language = payload.preferred_language
    db.commit()
    db.refresh(user)
    return user


@router.get("/notifications/settings")
def notification_settings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    preferences = get_preferences(db, user.id)
    db.commit()
    return preference_view(preferences)


@router.get("/notifications")
def notification_center(limit: int = Query(default=30, ge=1, le=100), unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return recent_notifications(db, user.id, limit, unread_only)


@router.get("/notifications/unread-count")
def notification_unread_count(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {"unread": unread_notification_count(db, user.id)}


@router.patch("/notifications/{notification_id}/read")
def read_notification(notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = mark_notification_read(db, user.id, notification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    return item


@router.post("/notifications/read-all")
def read_all_notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {"updated": mark_all_notifications_read(db, user.id)}


@router.put("/notifications/settings")
def update_notification_settings(payload: NotificationPreferenceUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    preferences = get_preferences(db, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(preferences, key, value)
    db.add(preferences)
    db.commit()
    db.refresh(preferences)
    return preference_view(preferences)


@router.get("/notifications/history")
def notification_history(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return recent_deliveries(db, user.id, limit)


@router.post("/notifications/test")
def test_notification_email(db: Session = Depends(get_db), user: User = Depends(current_user)):
    stamp = datetime.now(timezone.utc).isoformat()
    return send_notification(
        db, user, category="security_updates", event_key=f"test:{user.id}:{stamp}", force=True,
        subject_en="Agrinox email test",
        body_en=f"Hello {user.full_name},\n\nEmail notifications are working. This test did not change any farm data.",
        subject_rw="Igerageza rya imeyili ya Agrinox",
        body_rw=f"Muraho {user.full_name},\n\nAmatangazo ya imeyili arakora. Iri gerageza nta makuru y'umurima ryahinduye.",
    )


@router.get("/locations/reverse")
def location_reverse(latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180), db: Session = Depends(get_db), _user: User = Depends(current_user)):
    return reverse_geocode(db, latitude, longitude)


@router.get("/locations/search")
def location_search(q: str = Query(min_length=2, max_length=160), db: Session = Depends(get_db), _user: User = Depends(current_user)):
    return search_locations(db, q)


@router.get("/locations/provinces")
def location_provinces(db: Session = Depends(get_db), _user: User = Depends(current_user)):
    return options(db, Province)


@router.get("/locations/districts")
def location_districts(province_code: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
    return options(db, District, "province_code", province_code)


@router.get("/locations/sectors")
def location_sectors(district_code: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
    return options(db, Sector, "district_code", district_code)


@router.get("/locations/cells")
def location_cells(sector_code: str, db: Session = Depends(get_db), _user: User = Depends(current_user)):
    return options(db, Cell, "sector_code", sector_code)


@router.get("/locations/villages")
def location_villages(cell_code: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
    return options(db, Village, "cell_code", cell_code)


@router.get("/locations/cells/{cell_code}/map-focus")
def location_cell_map_focus(cell_code: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
    return cell_map_focus(db, cell_code)


@router.get("/weather")
def weather(
    farm_id: int | None = None,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    label: str | None = Query(default=None, max_length=160),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if farm_id is not None:
        farm = owned_farm(db, user.id, farm_id)
        if farm.latitude is not None and farm.longitude is not None:
            return weather_dashboard(db, farm.latitude, farm.longitude, farm.name, "farm coordinates")
        if farm.cell_code is not None:
            try:
                focus = cell_map_focus(db, farm.cell_code)
                return weather_dashboard(db, focus["latitude"], focus["longitude"], farm.name, f'{focus["focus_level"]} map reference')
            except HTTPException as exc:
                if exc.status_code not in (404, 503):
                    raise
        for query in (
            f"{farm.cell}, {farm.sector}, {farm.district}, Rwanda",
            f"{farm.sector}, {farm.district}, Rwanda",
            f"{farm.district}, Rwanda",
        ):
            matches = search_locations(db, query)
            if matches:
                match = matches[0]
                return weather_dashboard(db, match["latitude"], match["longitude"], farm.name, "administrative map reference")
        raise HTTPException(status_code=422, detail="This farm location could not be mapped for weather")
    if latitude is None or longitude is None:
        raise HTTPException(status_code=422, detail="Choose a farm or provide both latitude and longitude")
    return weather_dashboard(db, latitude, longitude, label or "Custom farm location", "provided coordinates")


@router.get("/farms", response_model=list[FarmOut])
def list_farms(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Farm).where(Farm.owner_id == user.id).options(selectinload(Farm.fields)).order_by(Farm.created_at.desc())).all()


@router.post("/farms", response_model=FarmOut, status_code=201)
def create_farm(payload: FarmCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    values = payload.model_dump()
    names = validate_hierarchy(db, province_code=payload.province_code, district_code=payload.district_code, sector_code=payload.sector_code, cell_code=payload.cell_code, village_code=payload.village_code)
    values.update(names)
    farm = Farm(owner_id=user.id, **values)
    db.add(farm)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="create", entity_type="farm", entity_id=farm.id))
    db.commit()
    db.refresh(farm)
    return farm


@router.put("/farms/{farm_id}", response_model=FarmOut)
def update_farm(farm_id: int, payload: FarmCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    farm = owned_farm(db, user.id, farm_id)
    values = payload.model_dump()
    names = validate_hierarchy(
        db,
        province_code=payload.province_code,
        district_code=payload.district_code,
        sector_code=payload.sector_code,
        cell_code=payload.cell_code,
        village_code=payload.village_code,
    )
    values.update(names)
    for key, value in values.items():
        setattr(farm, key, value)
    db.add(AuditLog(user_id=user.id, action="update", entity_type="farm", entity_id=farm.id))
    db.commit()
    db.refresh(farm)
    return farm


def owned_farm(db: Session, user_id: int, farm_id: int) -> Farm:
    farm = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.owner_id == user_id).options(selectinload(Farm.fields)))
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm


def owned_field(db: Session, user_id: int, field_id: int) -> FarmField:
    field = db.scalar(
        select(FarmField)
        .join(Farm)
        .where(FarmField.id == field_id, Farm.owner_id == user_id)
        .options(selectinload(FarmField.farm), selectinload(FarmField.soil_context))
    )
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return field


def satellite_request_area(db: Session, user_id: int, payload: SatelliteMonitorRequest):
    if payload.field_id is not None:
        field = owned_field(db, user_id, payload.field_id)
        if not field.boundary_geojson:
            raise HTTPException(status_code=422, detail="This field has no drawn map boundary. Draw its boundary or use searched-area mode.")
        try:
            geometry = json.loads(field.boundary_geojson)
        except (TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=422, detail="This field boundary is invalid") from exc
        return geometry, f"{field.name} · {field.farm.name}", "mapped_field"
    geometry = circle_geometry(payload.latitude, payload.longitude, payload.radius_m)
    return geometry, payload.label or f"Area near {payload.latitude:.5f}, {payload.longitude:.5f}", "searched_area"


def district_filters(
    year: int = Query(default=2026, ge=2024, le=2026),
    season: str = Query(default="A", pattern="^(A|B)$"),
    province: str | None = Query(default=None, max_length=80),
    district: str | None = Query(default=None, max_length=80),
    crop: str | None = Query(default="Maize", max_length=80),
    indicator: str = Query(default="production", max_length=80),
):
    return {"year": year, "season": season, "province": province, "district": district, "crop": crop, "indicator": indicator}


@router.get("/district-intelligence/options")
def get_district_options(_user: User = Depends(current_user)):
    return district_options()


@router.get("/district-intelligence/boundaries")
def get_district_boundaries(_user: User = Depends(current_user)):
    return district_boundaries()


@router.get("/district-intelligence/dashboard")
def get_district_dashboard(filters: dict = Depends(district_filters), _user: User = Depends(current_user)):
    try:
        return district_dashboard(**filters)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/district-intelligence/export.csv")
def export_district_csv(filters: dict = Depends(district_filters), _user: User = Depends(current_user)):
    try:
        content = district_csv_export(**filters)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(content=content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=nisr-district-aggregate.csv"})


@router.get("/district-intelligence/export.pdf")
def export_district_pdf(filters: dict = Depends(district_filters), _user: User = Depends(current_user)):
    try:
        content = district_pdf_export(**filters)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=nisr-district-intelligence.pdf"})


@router.get("/satellite/status")
def satellite_status(_user: User = Depends(current_user)):
    return integration_status()


@router.get("/satellite/areas")
def satellite_areas(db: Session = Depends(get_db), user: User = Depends(current_user)):
    areas = db.scalars(select(SatelliteArea).where(SatelliteArea.owner_id == user.id).order_by(SatelliteArea.created_at.desc())).all()
    return [{"id": area.id, "name": area.name, "latitude": area.latitude, "longitude": area.longitude, "radius_m": area.radius_m, "geometry": json.loads(area.geometry_geojson), "created_at": area.created_at.isoformat()} for area in areas]


@router.post("/satellite/areas", status_code=201)
def create_satellite_area(payload: SatelliteAreaCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    geometry = circle_geometry(payload.latitude, payload.longitude, payload.radius_m)
    area = SatelliteArea(owner_id=user.id, name=payload.name.strip(), latitude=payload.latitude, longitude=payload.longitude, radius_m=payload.radius_m, geometry_geojson=json.dumps(geometry))
    db.add(area)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="create", entity_type="satellite_area", entity_id=area.id))
    db.commit()
    db.refresh(area)
    return {"id": area.id, "name": area.name, "latitude": area.latitude, "longitude": area.longitude, "radius_m": area.radius_m, "geometry": geometry, "created_at": area.created_at.isoformat()}


@router.post("/satellite/dashboard")
def get_satellite_dashboard(payload: SatelliteMonitorRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    geometry, label, mode = satellite_request_area(db, user.id, payload)
    return satellite_dashboard(geometry, label, mode, payload.date_from, payload.date_to)


@router.post("/satellite/imagery")
def get_satellite_imagery(payload: SatelliteMonitorRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    geometry, _label, _mode = satellite_request_area(db, user.id, payload)
    if not integration_status()["configured"]:
        raise HTTPException(status_code=503, detail="Planet OAuth credentials are not configured")
    try:
        content = ndvi_image(geometry, payload.date_from, payload.date_to)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Sentinel-2 imagery is unavailable for this request") from exc
    return Response(content=content, media_type="image/png", headers={"Cache-Control": "private, max-age=1800"})


@router.get("/crop-planning/options")
def crop_planning_options(_user: User = Depends(current_user)):
    return planning_options()


@router.get("/crop-planning/plans")
def crop_planning_plans(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list_plans(db, user.id)


@router.post("/crop-planning/recommendations")
def crop_planning_recommendations(
    payload: CropRecommendationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    field = owned_field(db, user.id, payload.field_id)
    return recommend_crops(db, user.id, field, payload.season, payload.planned_planting_date)


@router.post("/crop-planning/plans", status_code=201)
def create_crop_plan(
    payload: CropPlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    available = planning_options()
    crop = next((item for item in available["crops"] if item.casefold() == payload.crop.strip().casefold()), None)
    if not crop:
        raise HTTPException(status_code=422, detail="Select a crop with verified NISR yield observations")
    if payload.season not in available["coverage_by_crop"][crop]:
        raise HTTPException(status_code=422, detail=f"No verified Season {payload.season} observations are curated for {crop}")
    payload.crop = crop
    field = owned_field(db, user.id, payload.field_id)
    result = save_plan(db, user.id, field, payload)
    db.add(AuditLog(user_id=user.id, action="create", entity_type="crop_plan", entity_id=result["plan_id"]))
    db.commit()
    send_notification(
        db, user, category="planning_updates", event_key=f"crop-plan-created:{result['plan_id']}",
        subject_en=f"Crop plan saved: {crop}",
        body_en=f"Your {crop} plan for {field.name}, Season {payload.season}, was saved. Planting date: {payload.planned_planting_date}. Open Crop Planning to review the evidence and limitations.",
        subject_rw=f"Igenamigambi ry'igihingwa ryabitswe: {crop}",
        body_rw=f"Igenamigambi rya {crop} ku gice {field.name}, Igihembwe {payload.season}, ryabitswe. Itariki yo gutera: {payload.planned_planting_date}. Fungura Igenamigambi ry'ibihingwa urebe ibimenyetso n'aho amakuru agarukira.",
    )
    return result


@router.post("/crop-planning/plans/{plan_id}/calendar", status_code=201)
def link_crop_plan_to_calendar(plan_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = db.scalar(
        select(CropPlan)
        .where(CropPlan.id == plan_id, CropPlan.owner_id == user.id)
        .options(
            selectinload(CropPlan.field).selectinload(FarmField.farm),
            selectinload(CropPlan.field).selectinload(FarmField.soil_context),
            selectinload(CropPlan.calendar_tasks).selectinload(CalendarTask.field).selectinload(FarmField.farm),
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Crop plan not found")
    if plan.calendar_tasks:
        return {
            "created": False,
            "plan_id": plan.id,
            "task_count": len(plan.calendar_tasks),
            "message": "This crop plan is already linked to the calendar.",
            "tasks": [calendar_task_view(task) for task in sorted(plan.calendar_tasks, key=lambda item: item.due_at)],
        }

    guidance = calendar_suggestions(
        plan.crop,
        plan.planned_planting_date,
        plan.field.soil_context.growth_stage if plan.field.soil_context else None,
    )
    created = []
    for item in guidance:
        task = CalendarTask(
            owner_id=user.id,
            field_id=plan.field_id,
            crop_plan_id=plan.id,
            title=item["title"],
            description=item["description"],
            category=item["category"],
            crop=item["crop"],
            growth_stage=item["growth_stage"],
            due_at=datetime.fromisoformat(item["due_at"]),
            reminder_at=datetime.fromisoformat(item["reminder_at"]),
            recurrence=item["recurrence"],
            recurrence_interval=item["recurrence_interval"],
            source_type="suggested",
            source_title=item["source_title"],
            source_url=item["source_url"],
        )
        db.add(task)
        created.append(task)
    db.flush()
    task_ids = [task.id for task in created]
    db.add(AuditLog(user_id=user.id, action="link_calendar", entity_type="crop_plan", entity_id=plan.id))
    db.commit()
    tasks = [calendar_task_view(get_calendar_task(db, user.id, task_id)) for task_id in task_ids]
    return {
        "created": True,
        "plan_id": plan.id,
        "task_count": len(tasks),
        "message": f"Added {len(tasks)} crop-plan tasks to the calendar.",
        "tasks": tasks,
    }


@router.get("/calendar/overview")
def get_calendar_overview(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return calendar_overview(db, user.id)


@router.get("/calendar/tasks")
def get_calendar_tasks(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    field_id: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(pending|completed)$"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if date_from and date_to and date_to < date_from:
        raise HTTPException(status_code=422, detail="End date must be after the start date")
    return list_calendar_tasks(db, user.id, date_from, date_to, field_id, status_filter)


@router.post("/calendar/tasks", status_code=201)
def create_calendar_task(payload: CalendarTaskCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_field(db, user.id, payload.field_id)
    task = CalendarTask(owner_id=user.id, **payload.model_dump())
    db.add(task)
    db.flush()
    task_id = task.id
    db.add(AuditLog(user_id=user.id, action="create", entity_type="calendar_task", entity_id=task_id))
    db.commit()
    return calendar_task_view(get_calendar_task(db, user.id, task_id))


@router.patch("/calendar/tasks/{task_id}")
def update_calendar_task(task_id: int, payload: CalendarTaskUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    task = get_calendar_task(db, user.id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Calendar task not found")
    values = payload.model_dump(exclude_unset=True)
    resulting_due = values.get("due_at", task.due_at)
    resulting_reminder = values.get("reminder_at", task.reminder_at)
    comparable_due = resulting_due.replace(tzinfo=None) if resulting_due.tzinfo else resulting_due
    comparable_reminder = resulting_reminder.replace(tzinfo=None) if resulting_reminder and resulting_reminder.tzinfo else resulting_reminder
    if comparable_reminder and comparable_reminder > comparable_due:
        raise HTTPException(status_code=422, detail="Reminder must be scheduled before the task is due")
    for key, value in values.items():
        setattr(task, key, value.strip() if isinstance(value, str) and key in {"title", "description", "crop", "growth_stage"} else value)
    task.reminder_dismissed = False
    task.email_sent_at = None
    db.add(AuditLog(user_id=user.id, action="update", entity_type="calendar_task", entity_id=task.id))
    db.commit()
    return calendar_task_view(get_calendar_task(db, user.id, task.id))


@router.post("/calendar/tasks/{task_id}/complete")
def mark_calendar_task_complete(task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    task = get_calendar_task(db, user.id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Calendar task not found")
    if task.status == "completed":
        return {"task": calendar_task_view(task), "next_task": None}
    next_task = complete_task(db, task)
    db.add(AuditLog(user_id=user.id, action="complete", entity_type="calendar_task", entity_id=task.id))
    db.commit()
    refreshed = get_calendar_task(db, user.id, task.id)
    next_view = calendar_task_view(get_calendar_task(db, user.id, next_task.id)) if next_task else None
    return {"task": calendar_task_view(refreshed), "next_task": next_view}


@router.post("/calendar/tasks/{task_id}/reopen")
def reopen_calendar_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    task = get_calendar_task(db, user.id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Calendar task not found")
    task.status = "pending"
    task.completed_at = None
    task.reminder_dismissed = False
    db.add(AuditLog(user_id=user.id, action="reopen", entity_type="calendar_task", entity_id=task.id))
    db.commit()
    return calendar_task_view(get_calendar_task(db, user.id, task.id))


@router.delete("/calendar/tasks/{task_id}", status_code=204)
def delete_calendar_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    task = get_calendar_task(db, user.id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Calendar task not found")
    db.delete(task)
    db.add(AuditLog(user_id=user.id, action="delete", entity_type="calendar_task", entity_id=task_id))
    db.commit()


@router.get("/calendar/reminders")
def get_calendar_reminders(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return calendar_reminders(db, user.id)


@router.post("/calendar/tasks/{task_id}/dismiss-reminder")
def dismiss_calendar_reminder(task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    task = get_calendar_task(db, user.id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Calendar task not found")
    task.reminder_dismissed = True
    db.commit()
    return {"dismissed": True, "task_id": task.id}


@router.post("/calendar/suggestions")
def get_calendar_suggestions(payload: CalendarSuggestionRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_field(db, user.id, payload.field_id)
    return calendar_suggestions(payload.crop, payload.planting_date, payload.growth_stage)


@router.post("/calendar/reminders/send-due")
def send_calendar_email_reminders(db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        return send_due_email_reminders(db, user)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(status_code=503, detail="Email reminder delivery is temporarily unavailable") from exc


@router.get("/finance/crop-plans")
def get_finance_crop_plans(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return finance_crop_plan_options(db, user.id)


@router.post("/finance/calculate")
def calculate_farm_finances(payload: FinancialCalculationRequest, _user: User = Depends(current_user)):
    return calculate_financials(
        payload.area_ha,
        payload.expected_harvest_kg,
        payload.selling_price_per_kg_rwf,
        [item.model_dump() for item in payload.expenses],
    )


@router.get("/finance/plans")
def get_financial_plans(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list_financial_plans(db, user.id)


@router.get("/finance/plans/{plan_id}")
def get_financial_plan_detail(plan_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = get_financial_plan(db, user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Financial plan not found")
    return financial_plan_view(plan)


@router.post("/finance/plans", status_code=201)
def create_financial_plan(payload: FinancialPlanCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_field(db, user.id, payload.field_id)
    if payload.crop_plan_id is not None:
        crop_plan = db.scalar(select(CropPlan).where(CropPlan.id == payload.crop_plan_id, CropPlan.owner_id == user.id))
        if not crop_plan:
            raise HTTPException(status_code=404, detail="Crop plan not found")
        if crop_plan.field_id != payload.field_id:
            raise HTTPException(status_code=422, detail="The crop plan belongs to a different field")
    expenses = [item.model_dump() for item in payload.expenses]
    result = calculate_financials(payload.area_ha, payload.expected_harvest_kg, payload.selling_price_per_kg_rwf, expenses)
    plan = FinancialPlan(
        owner_id=user.id,
        field_id=payload.field_id,
        crop_plan_id=payload.crop_plan_id,
        title=payload.title.strip(),
        crop=payload.crop.strip() if payload.crop else None,
        area_ha=payload.area_ha,
        expected_harvest_kg=payload.expected_harvest_kg,
        selling_price_per_kg_rwf=payload.selling_price_per_kg_rwf,
        expenses_json=json.dumps(expenses),
        result_json=json.dumps(result),
    )
    db.add(plan)
    db.flush()
    plan_id = plan.id
    db.add(AuditLog(user_id=user.id, action="create", entity_type="financial_plan", entity_id=plan_id))
    db.commit()
    send_notification(
        db, user, category="finance_updates", event_key=f"financial-plan-created:{plan_id}",
        subject_en=f"Financial plan saved: {plan.title}",
        body_en=f"Your financial plan was saved. Expected revenue: {result['expected_revenue_rwf']:,.0f} RWF. Expected expenses: {result['total_expenses_rwf']:,.0f} RWF. Expected profit: {result['expected_profit_rwf']:,.0f} RWF. These are estimates based on your entered harvest, price and costs.",
        subject_rw=f"Igenamigambi ry'amafaranga ryabitswe: {plan.title}",
        body_rw=f"Igenamigambi ry'amafaranga ryabitswe. Amafaranga ateganyijwe kwinjira: {result['expected_revenue_rwf']:,.0f} RWF. Ibiguzi biteganyijwe: {result['total_expenses_rwf']:,.0f} RWF. Inyungu iteganyijwe: {result['expected_profit_rwf']:,.0f} RWF. Iyi ni imibare ishingiye ku musaruro, igiciro n'ibiguzi wanditse.",
    )
    return financial_plan_view(get_financial_plan(db, user.id, plan_id))


@router.patch("/finance/plans/{plan_id}")
def update_financial_plan(plan_id: int, payload: FinancialPlanUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = get_financial_plan(db, user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Financial plan not found")
    values = payload.model_dump(exclude_unset=True)
    if "title" in values:
        plan.title = values["title"].strip()
    if "crop" in values:
        plan.crop = values["crop"].strip() if values["crop"] else None
    for key in ("area_ha", "expected_harvest_kg", "selling_price_per_kg_rwf"):
        if key in values:
            setattr(plan, key, values[key])
    expenses = values.get("expenses")
    if expenses is not None:
        expenses = [item if isinstance(item, dict) else item.model_dump() for item in expenses]
        plan.expenses_json = json.dumps(expenses)
    else:
        expenses = json.loads(plan.expenses_json)
    plan.result_json = json.dumps(calculate_financials(plan.area_ha, plan.expected_harvest_kg, plan.selling_price_per_kg_rwf, expenses))
    db.add(AuditLog(user_id=user.id, action="update", entity_type="financial_plan", entity_id=plan.id))
    db.commit()
    return financial_plan_view(get_financial_plan(db, user.id, plan.id))


@router.delete("/finance/plans/{plan_id}", status_code=204)
def delete_financial_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = get_financial_plan(db, user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Financial plan not found")
    db.delete(plan)
    db.add(AuditLog(user_id=user.id, action="delete", entity_type="financial_plan", entity_id=plan_id))
    db.commit()


@router.post("/finance/plans/{plan_id}/transactions", status_code=201)
def create_financial_transaction(plan_id: int, payload: FinancialTransactionCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = get_financial_plan(db, user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Financial plan not found")
    transaction = FinancialTransaction(owner_id=user.id, plan_id=plan.id, **payload.model_dump())
    db.add(transaction)
    db.flush()
    transaction_id = transaction.id
    db.add(AuditLog(user_id=user.id, action="create", entity_type="financial_transaction", entity_id=transaction_id))
    db.commit()
    transaction = db.scalar(select(FinancialTransaction).where(FinancialTransaction.id == transaction_id, FinancialTransaction.owner_id == user.id))
    send_notification(
        db, user, category="finance_updates", event_key=f"financial-transaction:{transaction_id}",
        subject_en=f"Farm {payload.kind} recorded",
        body_en=f"{payload.description}: {payload.amount_rwf:,.0f} RWF was recorded as {payload.kind} in {plan.title}. Open Farm Profit & Expenses to review the actual balance.",
        subject_rw=f"Amafaranga yo mu murima yanditswe: {payload.kind}",
        body_rw=f"{payload.description}: {payload.amount_rwf:,.0f} RWF yanditswe nka {payload.kind} muri {plan.title}. Fungura Inyungu n'ibyakoreshejwe urebe amafaranga nyayo.",
    )
    return financial_transaction_view(transaction)


@router.delete("/finance/transactions/{transaction_id}", status_code=204)
def delete_financial_transaction(transaction_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    transaction = db.scalar(select(FinancialTransaction).where(FinancialTransaction.id == transaction_id, FinancialTransaction.owner_id == user.id))
    if not transaction:
        raise HTTPException(status_code=404, detail="Financial transaction not found")
    db.delete(transaction)
    db.add(AuditLog(user_id=user.id, action="delete", entity_type="financial_transaction", entity_id=transaction_id))
    db.commit()


@router.get("/plant-lens/model-status")
def plant_lens_model_status(_user: User = Depends(current_user)):
    return model_status()


@router.get("/plant-lens/cases")
def plant_lens_cases(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list_cases(db, user.id)


@router.post("/plant-lens/analyze", status_code=201)
async def analyze_plant_photo(
    crop_id: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    content = await image.read(settings.plant_lens_max_upload_mb * 1024 * 1024 + 1)
    result = analyze_image(db, user.id, crop_id, image.filename or "plant-photo", content)
    db.add(AuditLog(user_id=user.id, action="analyze", entity_type="plant_lens_case", entity_id=result["id"]))
    db.commit()
    prediction = result.get("prediction") or {}
    condition = prediction.get("possible_condition") or "No supported condition reported"
    send_notification(
        db, user, category="plant_results", event_key=f"plant-lens-result:{result['id']}",
        subject_en=f"Plant Lens result: {result['crop_name']}",
        body_en=f"Plant Lens finished screening your {result['crop_name']} photograph.\n\nResult: {condition}\n\nThis is image screening, not a confirmed diagnosis. Open Plant Lens to review confidence, alternatives and inspection steps before taking treatment action.",
        subject_rw=f"Igisubizo cy'isuzuma ry'igihingwa: {result['crop_name']}",
        body_rw=f"Isuzuma ry'igihingwa ryarangije kureba ifoto ya {result['crop_name']}.\n\nIgisubizo: {condition}\n\nIri ni isuzuma ry'ifoto, si indwara yemejwe. Fungura Isuzuma ry'igihingwa urebe icyizere, ibindi bishoboka n'ibyo kugenzura mbere yo gukoresha umuti.",
    )
    return result


@router.get("/plant-lens/cases/{case_id}/image")
def plant_lens_case_image(case_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    case = db.scalar(select(PlantLensCase).where(PlantLensCase.id == case_id, PlantLensCase.owner_id == user.id))
    if not case:
        raise HTTPException(status_code=404, detail="Plant Lens case not found")
    path = Path(case.image_path).resolve()
    if not path.is_relative_to(UPLOAD_ROOT.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Stored image is unavailable")
    media_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(path.suffix.casefold(), "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=case.original_filename, content_disposition_type="inline")


@router.post("/plant-lens/cases/{case_id}/advice")
def plant_lens_case_advice(case_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    language = "rw" if user.preferred_language == "rw" else "en"
    advice = generate_case_advice(db, user.id, case_id, language)
    db.add(AuditLog(user_id=user.id, action="gemini_advice", entity_type="plant_lens_case", entity_id=case_id))
    db.commit()
    return advice


@router.patch("/plant-lens/cases/{case_id}")
def review_plant_lens_case(case_id: int, payload: PlantLensReviewUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    case = db.scalar(select(PlantLensCase).where(PlantLensCase.id == case_id, PlantLensCase.owner_id == user.id))
    if not case:
        raise HTTPException(status_code=404, detail="Plant Lens case not found")
    case.review_status = payload.review_status
    case.reviewed_at = datetime.now(timezone.utc)
    db.add(AuditLog(user_id=user.id, action="review", entity_type="plant_lens_case", entity_id=case.id))
    db.commit()
    return case_view(case)


def device_view(device: Device) -> dict:
    now = datetime.now(timezone.utc)
    last_seen = device.last_seen_at
    if last_seen and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    seconds_since_seen = max(0, int((now - last_seen).total_seconds())) if last_seen else None
    is_online = (
        device.status != "offline"
        and seconds_since_seen is not None
        and seconds_since_seen <= settings.device_offline_after_seconds
    )
    return {
        "id": device.id,
        "field_id": device.field_id,
        "field_name": device.field.name if device.field else None,
        "farm_id": device.field.farm_id if device.field else None,
        "farm_name": device.field.farm.name if device.field else None,
        "name": device.name,
        "device_uid": device.device_uid,
        "board": device.board,
        "port": device.port,
        "baud_rate": device.baud_rate,
        "firmware_version": device.firmware_version,
        "status": "online" if is_online else "offline",
        "is_online": is_online,
        "last_seen_seconds_ago": seconds_since_seen,
        "offline_after_seconds": settings.device_offline_after_seconds,
        "last_seen_at": device.last_seen_at,
        "created_at": device.created_at,
        "device_credentials_configured": bool(device.api_key_hash),
        "remote_control_enabled": device.remote_control_enabled,
        "sensors": [{
            "id": sensor.id,
            "key": sensor.sensor_key,
            "name": sensor.name,
            "type": sensor.sensor_type,
            "unit": sensor.unit,
            "pin": sensor.pin,
            "latest_value": sensor.latest_value,
            "last_read_at": sensor.last_read_at,
        } for sensor in device.sensors],
    }


@router.get("/iot/devices")
def iot_devices(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list_devices(db, user)


@router.post("/iot/devices/{device_id}/credentials")
def create_device_credentials(device_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    device = db.scalar(select(Device).where(Device.id == device_id, Device.owner_id == user.id))
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    key = provision_device_key(device)
    db.add(AuditLog(user_id=user.id, action="provision_credentials", entity_type="device", entity_id=device.id))
    db.commit()
    return {"device_uid": device.device_uid, "device_key": key, "warning": "This key is shown once. Store it in ESP32 secure configuration."}


@router.patch("/iot/devices/{device_id}/remote-control")
def set_device_remote_control(device_id: int, enabled: bool, db: Session = Depends(get_db), user: User = Depends(current_user)):
    device = db.scalar(select(Device).where(Device.id == device_id, Device.owner_id == user.id))
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.remote_control_enabled = enabled
    db.add(AuditLog(user_id=user.id, action="enable_remote_control" if enabled else "disable_remote_control", entity_type="device", entity_id=device.id))
    db.commit()
    send_notification(
        db, user, category="security_updates", event_key=f"device-remote-control:{device.id}:{enabled}:{datetime.now(timezone.utc).isoformat()}",
        subject_en=f"Remote device control {'enabled' if enabled else 'disabled'}",
        body_en=f"Remote control was {'enabled' if enabled else 'disabled'} for {device.name}. Review Smart Irrigation safety settings if you did not make this change.",
        subject_rw=f"Kugenzura igikoresho uri kure {'byemewe' if enabled else 'byahagaritswe'}",
        body_rw=f"Kugenzura {device.name} uri kure {'byemewe' if enabled else 'byahagaritswe'}. Suzuma igenamiterere ry'umutekano ryo Kuhira neza niba atari wowe wabihinduye.",
    )
    return {"device_id": device.id, "remote_control_enabled": device.remote_control_enabled}


@router.post("/iot/readings")
def post_iot_readings(
    payload: IoTReadingBatch,
    x_device_id: str = Header(alias="X-Device-ID"),
    x_device_key: str = Header(alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    device = authenticate_device(db, x_device_id, x_device_key)
    return ingest_readings(db, device, payload)


@router.post("/iot/heartbeat")
def device_heartbeat(
    payload: IoTHeartbeat,
    x_device_id: str = Header(alias="X-Device-ID"),
    x_device_key: str = Header(alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    device = authenticate_device(db, x_device_id, x_device_key)
    now = datetime.now(timezone.utc)
    device.last_seen_at = now
    device.status = "connected"
    if payload.firmware_version:
        device.firmware_version = payload.firmware_version
    db.commit()
    return {
        "status": "online",
        "received_at": now.isoformat(),
        "next_heartbeat_seconds": 30,
    }


@router.get("/iot/commands")
def device_commands(
    x_device_id: str = Header(alias="X-Device-ID"),
    x_device_key: str = Header(alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    device = authenticate_device(db, x_device_id, x_device_key)
    return pending_device_commands(db, device)


@router.get("/iot/config")
def device_irrigation_config(
    x_device_id: str = Header(alias="X-Device-ID"),
    x_device_key: str = Header(alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    device = authenticate_device(db, x_device_id, x_device_key)
    if not device.field_id:
        raise HTTPException(status_code=409, detail="Device is not assigned to a field")
    config = get_or_create_config(db, device.field_id)
    return {
        **config_view(config),
        "device_remote_control_enabled": device.remote_control_enabled,
        "command_ttl_minutes": COMMAND_TTL_MINUTES,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "fail_safe": "pump_off",
    }


@router.post("/iot/automatic/evaluate")
def evaluate_automatic_irrigation(
    x_device_id: str = Header(alias="X-Device-ID"),
    x_device_key: str = Header(alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    device = authenticate_device(db, x_device_id, x_device_key)
    if not device.field_id:
        raise HTTPException(status_code=409, detail="Device is not assigned to a field")
    field = owned_field(db, device.owner_id, device.field_id)
    payload = SimpleNamespace(command="start", duration_seconds=None, simulated=False)
    command = create_command(db, field, None, payload, source="automatic")
    db.add(AuditLog(user_id=device.owner_id, action="automatic_start", entity_type="irrigation_command", entity_id=command["id"]))
    db.commit()
    owner = db.get(User, device.owner_id)
    if owner:
        send_notification(
            db, owner, category="irrigation_events", event_key=f"irrigation-command-issued:{command['id']}",
            subject_en="Automatic irrigation command issued",
            body_en=f"Agrinox issued an automatic irrigation start command for {field.name}. Status: {command['status']}. Open Smart Irrigation to review sensor evidence and safety status.",
            subject_rw="Itegeko ryo kuhira ryikoresha ryatanzwe",
            body_rw=f"Agrinox yatanze itegeko ryikoresha ryo gutangira kuhira {field.name}. Uko rihagaze: {command['status']}. Fungura Kuhira neza urebe ibipimo bya sensori n'umutekano.",
        )
    return command


@router.post("/iot/commands/{command_id}/status")
def update_device_command_status(
    command_id: int,
    payload: DeviceCommandStatus,
    x_device_id: str = Header(alias="X-Device-ID"),
    x_device_key: str = Header(alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    device = authenticate_device(db, x_device_id, x_device_key)
    command = db.scalar(select(IrrigationCommand).where(IrrigationCommand.id == command_id, IrrigationCommand.device_id == device.id))
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
    allowed_transition = command.status == "pending" or (command.status == "executed" and command.command == "start" and payload.status in {"completed", "failed"})
    if not allowed_transition:
        raise HTTPException(status_code=409, detail=f"Command is already {command.status}")
    if command.status == "pending" and command.command == "start" and datetime.now(timezone.utc) - command.issued_at.replace(tzinfo=timezone.utc) > timedelta(minutes=COMMAND_TTL_MINUTES):
        command.status = "rejected"
        command.execution_message = "Start command expired; pump must remain OFF"
        command.executed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=409, detail="Start command expired; keep the pump OFF")
    command.status = payload.status
    command.execution_message = payload.message
    command.executed_at = datetime.now(timezone.utc)
    db.commit()
    owner = db.get(User, device.owner_id)
    if owner:
        action = "started" if command.command == "start" and payload.status == "executed" else "completed" if command.command == "start" and payload.status == "completed" else "stopped" if command.command in {"stop", "emergency_stop"} else payload.status
        send_notification(
            db, owner, category="irrigation_events", event_key=f"irrigation-command-status:{command.id}:{payload.status}",
            subject_en=f"Irrigation {action}", body_en=f"Irrigation command #{command.id} for field {command.field_id} is now {payload.status}.\n\nDevice message: {payload.message or 'No device message.'}",
            subject_rw=f"Kuhira: {action}", body_rw=f"Itegeko ryo kuhira #{command.id} ku gice cy'umurima {command.field_id} ubu riri: {payload.status}.\n\nUbutumwa bw'igikoresho: {payload.message or 'Nta butumwa bwatanzwe.'}",
        )
    return command_view(command)


@router.get("/irrigation/status")
def get_irrigation_status(field_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return irrigation_status(db, owned_field(db, user.id, field_id))


@router.put("/irrigation/config")
def update_irrigation_config(payload: IrrigationConfigUpdate, field_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_field(db, user.id, field_id)
    if payload.mode == "automatic" and not payload.safety_validated:
        raise HTTPException(status_code=422, detail="Automatic mode requires explicit safety validation")
    config = get_or_create_config(db, field_id)
    for key, value in payload.model_dump().items():
        setattr(config, key, value)
    db.add(AuditLog(user_id=user.id, action="update", entity_type="irrigation_config", entity_id=config.id))
    db.commit()
    return config_view(config)


@router.post("/irrigation/commands", status_code=201)
def post_irrigation_command(payload: IrrigationCommandCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    field = owned_field(db, user.id, payload.field_id)
    command = create_command(db, field, user.id, payload)
    db.add(AuditLog(user_id=user.id, action=payload.command, entity_type="irrigation_command", entity_id=command["id"]))
    db.commit()
    command_label = {"start": "started", "stop": "stopped", "emergency_stop": "emergency-stopped"}.get(payload.command, payload.command)
    send_notification(
        db, user, category="irrigation_events", event_key=f"irrigation-command-issued:{command['id']}",
        subject_en=f"Irrigation command issued: {command_label}",
        body_en=f"A {payload.command} command was issued for {field.name}. Status: {command['status']}. Source: {command['source']}. Open Smart Irrigation to follow execution and safety status.",
        subject_rw=f"Itegeko ryo kuhira ryatanzwe: {command_label}",
        body_rw=f"Itegeko rya {payload.command} ryatanzwe ku gice {field.name}. Uko rihagaze: {command['status']}. Inkomoko: {command['source']}. Fungura Kuhira neza ukurikirane ishyirwa mu bikorwa n'umutekano.",
    )
    return command


@router.get("/soil/fields/{field_id}")
def get_soil_dashboard(field_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    field = db.scalar(
        select(FarmField).join(Farm).where(FarmField.id == field_id, Farm.owner_id == user.id)
        .options(selectinload(FarmField.farm), selectinload(FarmField.soil_context))
    )
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return soil_dashboard(db, field, user.id)


@router.put("/soil/fields/{field_id}/context")
def update_soil_context(field_id: int, payload: SoilContextUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    field = owned_field(db, user.id, field_id)
    context = db.scalar(select(SoilContext).where(SoilContext.field_id == field.id))
    if not context:
        context = SoilContext(field_id=field.id)
        db.add(context)
    context.crop_type = payload.crop_type.strip() if payload.crop_type else None
    context.growth_stage = payload.growth_stage.strip() if payload.growth_stage else None
    db.add(AuditLog(user_id=user.id, action="update", entity_type="soil_context", entity_id=field.id))
    db.commit()
    return {"crop_type": context.crop_type, "growth_stage": context.growth_stage}


@router.post("/soil/fields/{field_id}/readings", status_code=201)
def create_soil_readings(field_id: int, payload: SoilReadingCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_field(db, user.id, field_id)
    measured_at = payload.measured_at or datetime.now(timezone.utc)
    if measured_at.tzinfo is None:
        measured_at = measured_at.replace(tzinfo=timezone.utc)
    if measured_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Reading time cannot be in the future")
    created = []
    for item in payload.measurements:
        if item.measurement_type in ("nitrogen", "phosphorus", "potassium") and item.value < 0:
            raise HTTPException(status_code=422, detail="Soil nutrient values cannot be negative")
        if item.measurement_type == "ph" and not 0 <= item.value <= 14:
            raise HTTPException(status_code=422, detail="Soil pH must be between 0 and 14")
        if item.measurement_type == "moisture" and item.unit == "%" and not 0 <= item.value <= 100:
            raise HTTPException(status_code=422, detail="Soil moisture percentage must be between 0 and 100")
        if item.measurement_type == "temperature" and item.unit.strip().lower() in ("°c", "c", "celsius") and not -10 <= item.value <= 70:
            raise HTTPException(status_code=422, detail="Soil temperature in Celsius must be between -10 and 70")
        calibration_status = "not_applicable" if payload.source == "laboratory" else item.calibration_status
        reliability = "reliable" if payload.source == "laboratory" else item.reliability
        reading = SoilReading(
            owner_id=user.id, field_id=field_id, measurement_type=item.measurement_type,
            value=item.value, unit=item.unit.strip(), source=payload.source,
            calibration_status=calibration_status, reliability=reliability,
            note=payload.note.strip() if payload.note else None, measured_at=measured_at,
        )
        db.add(reading)
        created.append(reading)
    db.add(AuditLog(user_id=user.id, action="create", entity_type="soil_reading", entity_id=field_id))
    db.commit()
    warnings = []
    for item in payload.measurements:
        if item.measurement_type == "moisture" and item.unit == "%" and item.value < 20:
            warnings.append(f"soil moisture {item.value:g}%")
        elif item.measurement_type == "temperature" and item.unit.strip().lower() in ("°c", "c", "celsius") and item.value > 35:
            warnings.append(f"soil temperature {item.value:g}°C")
        elif item.measurement_type == "ph" and (item.value < 4.5 or item.value > 8.5):
            warnings.append(f"soil pH {item.value:g}")
    if warnings:
        field = owned_field(db, user.id, field_id)
        evidence = ", ".join(warnings)
        send_notification(
            db, user, category="soil_alerts", event_key=f"soil-alert:{field_id}:{measured_at.isoformat()}:{'-'.join(sorted(warnings))}",
            subject_en=f"Soil reading needs review: {field.name}",
            body_en=f"A new reading on {field.name} needs attention: {evidence}. Check the field and Soil Quality advice. Low-cost sensor readings must be calibrated; do not make a precise fertilizer or treatment decision from this email alone.",
            subject_rw=f"Igipimo cy'ubutaka gikeneye gusuzumwa: {field.name}",
            body_rw=f"Igipimo gishya kuri {field.name} gikeneye kwitabwaho: {evidence}. Genzura umurima n'inama z'Ubwiza bw'ubutaka. Ibipimo bya sensori zoroheje bigomba gukorerwa kaliburasiyo; ntufate icyemezo nyacyo cy'ifumbire cyangwa umuti ushingiye kuri iyi meyili yonyine.",
        )
    return {"created": len(created), "field_id": field_id}


@router.get("/devices/scan")
def scan_devices(probe: bool = True, _user: User = Depends(current_user)):
    return scan_usb_ports(probe=probe)


@router.post("/devices/firmware/install", status_code=201)
def install_device_firmware(
    payload: FirmwareInstallRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    try:
        discovered = flash_firmware(payload.port)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    device_uid = str(discovered.get("device_uid") or "").strip()
    if not device_uid:
        raise HTTPException(status_code=502, detail="Firmware installed, but the ESP32 did not report its identity")
    device = db.scalar(
        select(Device).where(Device.device_uid == device_uid)
        .options(selectinload(Device.sensors), selectinload(Device.field).selectinload(FarmField.farm))
    )
    if device and device.owner_id != user.id:
        raise HTTPException(status_code=409, detail="This ESP32 is registered to another account")
    if device is None:
        suffix = "".join(character for character in device_uid if character.isalnum())[-6:].upper()
        device = Device(
            owner_id=user.id,
            field_id=None,
            name=f"NPK Monitor {suffix or 'ESP32'}",
            device_uid=device_uid,
            board=str(discovered.get("board") or "ESP32 NPK monitor")[:80],
            port=payload.port,
            baud_rate=115200,
            firmware_version=str(discovered.get("firmware") or "agrinox-npk")[:80],
            status="connected",
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(device)
        db.flush()
    else:
        device.port = payload.port
        device.status = "connected"
        device.last_seen_at = datetime.now(timezone.utc)
        device.firmware_version = str(discovered.get("firmware") or device.firmware_version or "agrinox-npk")[:80]

    known_sensors = {sensor.sensor_key: sensor for sensor in device.sensors}
    for item in discovered.get("sensors") or []:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        sensor = known_sensors.get(key)
        if sensor is None:
            sensor = Sensor(device_id=device.id, sensor_key=key)
            device.sensors.append(sensor)
        sensor.name = str(item.get("name") or key.replace("_", " ").title())[:120]
        sensor.sensor_type = str(item.get("type") or key)[:80]
        sensor.unit = str(item.get("unit"))[:30] if item.get("unit") is not None else None
        sensor.pin = str(item.get("pin"))[:30] if item.get("pin") is not None else None

    device_key = provision_device_key(device)
    try:
        configure_firmware(
            payload.port,
            payload.wifi_ssid.strip(),
            payload.wifi_password.get_secret_value(),
            local_device_api_url(settings.device_api_base_url),
            device_key,
        )
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Firmware was installed, but Wi-Fi configuration failed: {exc}") from exc

    db.add(AuditLog(user_id=user.id, action="install_firmware", entity_type="device", entity_id=device.id))
    db.commit()
    installed = db.scalar(
        select(Device).where(Device.id == device.id)
        .options(selectinload(Device.sensors), selectinload(Device.field).selectinload(FarmField.farm))
    )
    return {
        "device": device_view(installed),
        "message": "Firmware installed and Wi-Fi configuration saved.",
        "field_assignment_required": installed.field_id is None,
    }


@router.get("/devices")
def list_devices(db: Session = Depends(get_db), user: User = Depends(current_user)):
    devices = db.scalars(
        select(Device).where(Device.owner_id == user.id)
        .options(selectinload(Device.sensors), selectinload(Device.field).selectinload(FarmField.farm))
        .order_by(Device.created_at.desc())
    ).all()
    return [device_view(device) for device in devices]


@router.get("/devices/{device_id}")
def get_device(device_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    device = db.scalar(
        select(Device).where(Device.id == device_id, Device.owner_id == user.id)
        .options(selectinload(Device.sensors), selectinload(Device.field).selectinload(FarmField.farm))
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device_view(device)


@router.post("/devices", status_code=201)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    field = owned_field(db, user.id, payload.field_id)
    existing = db.scalar(
        select(Device).where(Device.device_uid == payload.device_uid)
        .options(selectinload(Device.sensors), selectinload(Device.field).selectinload(FarmField.farm))
    )
    if existing:
        if existing.owner_id != user.id:
            raise HTTPException(status_code=409, detail="This device is registered to another account")
        existing.field = field
        existing.port = payload.port
        existing.baud_rate = payload.baud_rate
        existing.status = "connected"
        existing.last_seen_at = datetime.now(timezone.utc)
        if payload.firmware_version:
            existing.firmware_version = payload.firmware_version
        known_sensors = {sensor.sensor_key: sensor for sensor in existing.sensors}
        for item in payload.sensors:
            sensor = known_sensors.get(item.key)
            if sensor is None:
                sensor = Sensor(device_id=existing.id, sensor_key=item.key)
                existing.sensors.append(sensor)
            sensor.name = item.name
            sensor.sensor_type = item.type
            sensor.unit = item.unit
            sensor.pin = item.pin
        db.add(AuditLog(user_id=user.id, action="assign", entity_type="device", entity_id=existing.id))
        db.commit()
        db.expire_all()
        assigned = db.scalar(
            select(Device).where(Device.id == existing.id)
            .options(selectinload(Device.sensors), selectinload(Device.field).selectinload(FarmField.farm))
        )
        send_notification(
            db, user, category="device_alerts", event_key=f"device-assigned:{assigned.id}:{field.id}",
            subject_en=f"Device assigned: {assigned.name}",
            body_en=f"{assigned.name} is now assigned to {field.name}. Open Device Management to review its sensor readings.",
            subject_rw=f"Igikoresho cyashyizwe ku gice: {assigned.name}",
            body_rw=f"{assigned.name} cyashyizwe kuri {field.name}. Fungura Gucunga ibikoresho urebe ibipimo bya sensori.",
        )
        return device_view(assigned)
    device = Device(
        owner_id=user.id, field_id=payload.field_id, name=payload.name.strip(), device_uid=payload.device_uid.strip(),
        board=payload.board, port=payload.port, baud_rate=payload.baud_rate, firmware_version=payload.firmware_version,
        status="connected", last_seen_at=datetime.now(timezone.utc),
    )
    db.add(device)
    db.flush()
    for item in payload.sensors:
        db.add(Sensor(device_id=device.id, sensor_key=item.key, name=item.name, sensor_type=item.type, unit=item.unit, pin=item.pin))
    db.add(AuditLog(user_id=user.id, action="create", entity_type="device", entity_id=device.id))
    db.commit()
    device = db.scalar(select(Device).where(Device.id == device.id).options(selectinload(Device.sensors), selectinload(Device.field).selectinload(FarmField.farm)))
    send_notification(
        db, user, category="device_alerts", event_key=f"device-registered:{device.id}",
        subject_en=f"Device registered: {device.name}",
        body_en=f"{device.name} was registered and assigned to {device.field.name if device.field else 'no field'}. Sensors detected: {len(device.sensors)}. Open Device Management to review readings and permissions.",
        subject_rw=f"Igikoresho cyanditswe: {device.name}",
        body_rw=f"{device.name} cyanditswe kandi gishyirwa kuri {device.field.name if device.field else 'nta gice cy’umurima'}. Sensori zabonetse: {len(device.sensors)}. Fungura Gucunga ibikoresho urebe ibipimo n'uburenganzira.",
    )
    return device_view(device)


@router.patch("/devices/{device_id}")
def update_device(device_id: int, payload: DeviceUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    device = db.scalar(
        select(Device).where(Device.id == device_id, Device.owner_id == user.id)
        .options(selectinload(Device.sensors), selectinload(Device.field).selectinload(FarmField.farm))
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if "name" in payload.model_fields_set and payload.name is not None:
        device.name = payload.name.strip()
    if "field_id" in payload.model_fields_set:
        if payload.field_id is not None:
            device.field = owned_field(db, user.id, payload.field_id)
        else:
            device.field = None
    db.add(AuditLog(user_id=user.id, action="update", entity_type="device", entity_id=device.id))
    db.commit()
    device = db.scalar(
        select(Device).where(Device.id == device.id)
        .options(selectinload(Device.sensors), selectinload(Device.field).selectinload(FarmField.farm))
    )
    return device_view(device)


@router.post("/devices/{device_id}/read")
def read_device(device_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    device = db.scalar(select(Device).where(Device.id == device_id, Device.owner_id == user.id).options(selectinload(Device.sensors), selectinload(Device.field).selectinload(FarmField.farm)))
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    try:
        payload = exchange(device.port, "AGRINOX_READ", device.baud_rate)
        readings = payload.get("readings", {})
        now = datetime.now(timezone.utc)
        for sensor in device.sensors:
            if sensor.sensor_key not in readings:
                continue
            value = float(readings[sensor.sensor_key])
            sensor.latest_value = value
            sensor.last_read_at = now
            db.add(SensorReading(sensor_id=sensor.id, value=value, recorded_at=now))
        device.status = "connected"
        device.last_seen_at = now
        db.commit()
    except Exception as exc:
        device.status = "offline"
        db.commit()
        send_notification(
            db, user, category="device_alerts", event_key=f"device-offline:{device.id}:{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H')}",
            subject_en=f"Device connection failed: {device.name}",
            body_en=f"Agrinox could not read {device.name}; it is marked offline. Check power, USB or network connectivity before relying on its sensor readings.",
            subject_rw=f"Igikoresho nticyashoboye guhuzwa: {device.name}",
            body_rw=f"Agrinox ntiyashoboye gusoma {device.name}; cyashyizwe kuri offline. Genzura umuriro, USB cyangwa murandasi mbere yo kwishingikiriza ku bipimo byacyo.",
        )
        raise HTTPException(status_code=503, detail=f"Could not read device: {exc}") from exc
    db.refresh(device)
    return device_view(device)


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(device_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    device = db.scalar(select(Device).where(Device.id == device_id, Device.owner_id == user.id))
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.add(AuditLog(user_id=user.id, action="delete", entity_type="device", entity_id=device_id))
    db.commit()


@router.delete("/farms/{farm_id}", status_code=204)
def delete_farm(farm_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    farm = owned_farm(db, user.id, farm_id)
    db.delete(farm)
    db.add(AuditLog(user_id=user.id, action="delete", entity_type="farm", entity_id=farm_id))
    db.commit()


@router.post("/farms/{farm_id}/fields", response_model=FieldOut, status_code=201)
def create_field(farm_id: int, payload: FieldCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_farm(db, user.id, farm_id)
    side_values = [None, None, None, None]
    if all(v is not None for v in (payload.side_a, payload.side_b, payload.side_c, payload.side_d)):
        side_values, manual = manual_area(payload.side_a, payload.side_b, payload.side_c, payload.side_d, payload.side_unit)
    else:
        manual = None
    if payload.boundary_geojson:
        try:
            area, source = polygon_area_m2(payload.boundary_geojson), "map"
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        area, source = manual, "manual_estimate"
    field = FarmField(
        farm_id=farm_id, name=payload.name.strip(), crop_note=payload.crop_note,
        side_a_m=side_values[0], side_b_m=side_values[1], side_c_m=side_values[2], side_d_m=side_values[3],
        area_m2=area, area_source=source,
        boundary_geojson=json.dumps(payload.boundary_geojson) if payload.boundary_geojson else None,
    )
    db.add(field)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="create", entity_type="farm_field", entity_id=field.id))
    db.commit()
    db.refresh(field)
    return field


@router.put("/farms/{farm_id}/fields/{field_id}", response_model=FieldOut)
def update_field(
    farm_id: int,
    field_id: int,
    payload: FieldCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    owned_farm(db, user.id, farm_id)
    field = db.scalar(select(FarmField).where(FarmField.id == field_id, FarmField.farm_id == farm_id))
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    side_values = [None, None, None, None]
    if all(value is not None for value in (payload.side_a, payload.side_b, payload.side_c, payload.side_d)):
        side_values, manual = manual_area(
            payload.side_a,
            payload.side_b,
            payload.side_c,
            payload.side_d,
            payload.side_unit,
        )
    else:
        manual = None
    if payload.boundary_geojson:
        try:
            area, source = polygon_area_m2(payload.boundary_geojson), "map"
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        area, source = manual, "manual_estimate"
    field.name = payload.name.strip()
    field.crop_note = payload.crop_note
    field.side_a_m, field.side_b_m, field.side_c_m, field.side_d_m = side_values
    field.area_m2 = area
    field.area_source = source
    field.boundary_geojson = json.dumps(payload.boundary_geojson) if payload.boundary_geojson else None
    db.add(AuditLog(user_id=user.id, action="update", entity_type="farm_field", entity_id=field.id))
    db.commit()
    db.refresh(field)
    return field


@router.delete("/farms/{farm_id}/fields/{field_id}", status_code=204)
def delete_field(farm_id: int, field_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_farm(db, user.id, farm_id)
    field = db.scalar(select(FarmField).where(FarmField.id == field_id, FarmField.farm_id == farm_id))
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    db.delete(field)
    db.add(AuditLog(user_id=user.id, action="delete", entity_type="farm_field", entity_id=field_id))
    db.commit()


@router.get("/fields/{field_id}/water-sources")
def field_water_sources(field_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_field(db, user.id, field_id)
    return {
        "sources": [source_view(db, item) for item in list_sources(db, field_id)],
        "compatible_sensors": compatible_sensors(db, field_id),
    }


@router.post("/fields/{field_id}/water-sources", status_code=201)
def create_water_source(field_id: int, payload: WaterSourceCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_field(db, user.id, field_id)
    sensor = validate_sensor(db, field_id, payload.sensor_id)
    existing = list_sources(db, field_id)
    source = WaterSource(
        field_id=field_id,
        sensor_id=sensor.id if sensor else None,
        name=payload.name.strip(),
        source_type=payload.source_type,
        capacity_liters=payload.capacity_liters if payload.source_type == "tank" else None,
        tank_height_cm=payload.tank_height_cm if payload.source_type == "tank" else None,
        notes=payload.notes.strip() if payload.notes else None,
        is_primary=payload.is_primary or not existing,
    )
    db.add(source)
    db.flush()
    if source.is_primary:
        set_primary(db, field_id, source)
    db.add(AuditLog(user_id=user.id, action="create", entity_type="water_source", entity_id=source.id))
    db.commit()
    source = db.scalar(select(WaterSource).where(WaterSource.id == source.id).options(selectinload(WaterSource.sensor)))
    return source_view(db, source)


@router.patch("/fields/{field_id}/water-sources/{source_id}")
def update_water_source(field_id: int, source_id: int, payload: WaterSourceUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_field(db, user.id, field_id)
    source = db.scalar(select(WaterSource).where(WaterSource.id == source_id, WaterSource.field_id == field_id).options(selectinload(WaterSource.sensor)))
    if not source:
        raise HTTPException(status_code=404, detail="Water source not found")
    changes = payload.model_dump(exclude_unset=True)
    if source.source_type != "tank" and any(changes.get(key) is not None for key in ("capacity_liters", "tank_height_cm", "sensor_id")):
        raise HTTPException(status_code=422, detail="Capacity, tank height and level sensor can only be set for a tank")
    if "sensor_id" in changes:
        sensor = validate_sensor(db, field_id, changes.pop("sensor_id"), source.id)
        source.sensor_id = sensor.id if sensor else None
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "notes" in changes and changes["notes"]:
        changes["notes"] = changes["notes"].strip()
    make_primary = bool(changes.pop("is_primary", False))
    for key, value in changes.items():
        setattr(source, key, value)
    if make_primary:
        set_primary(db, field_id, source)
    if source.is_primary and not source.is_active:
        source.is_primary = False
        replacement = db.scalar(select(WaterSource).where(WaterSource.field_id == field_id, WaterSource.id != source.id, WaterSource.is_active.is_(True)).order_by(WaterSource.created_at))
        if replacement:
            set_primary(db, field_id, replacement)
    db.add(AuditLog(user_id=user.id, action="update", entity_type="water_source", entity_id=source.id))
    db.commit()
    source = db.scalar(select(WaterSource).where(WaterSource.id == source.id).options(selectinload(WaterSource.sensor)))
    return source_view(db, source)


@router.delete("/fields/{field_id}/water-sources/{source_id}", status_code=204)
def delete_water_source(field_id: int, source_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    owned_field(db, user.id, field_id)
    source = db.scalar(select(WaterSource).where(WaterSource.id == source_id, WaterSource.field_id == field_id))
    if not source:
        raise HTTPException(status_code=404, detail="Water source not found")
    was_primary = source.is_primary
    db.delete(source)
    db.flush()
    if was_primary:
        replacement = db.scalar(select(WaterSource).where(WaterSource.field_id == field_id, WaterSource.is_active.is_(True)).order_by(WaterSource.created_at))
        if replacement:
            set_primary(db, field_id, replacement)
    db.add(AuditLog(user_id=user.id, action="delete", entity_type="water_source", entity_id=source_id))
    db.commit()


@router.get("/knowledge/overview")
def knowledge_overview(db: Session = Depends(get_db), _user: User = Depends(current_user)):
    seed_knowledge(db)
    articles = db.scalars(select(KnowledgeArticle)).all()
    categories = sorted({article.category for article in articles})
    return {
        "article_count": len(articles),
        "verified_count": sum(article.review_status in ("source_verified", "agronomist_reviewed") for article in articles),
        "categories": categories,
        "ai_available": bool(settings.gemini_api_key),
        "model": settings.gemini_model if settings.gemini_api_key else None,
    }


@router.get("/knowledge/articles")
def list_knowledge_articles(
    q: str = Query(default="", max_length=200),
    category: str | None = Query(default=None, max_length=80),
    language: str = Query(default="en", pattern="^(en|rw)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(current_user),
):
    seed_knowledge(db)
    articles = db.scalars(
        select(KnowledgeArticle).options(selectinload(KnowledgeArticle.sources)).order_by(KnowledgeArticle.title_en)
    ).all()
    query = q.strip().lower()
    filtered = []
    for article in articles:
        if category and article.category != category:
            continue
        haystack = f"{article.title_en} {article.title_rw} {article.content_en} {article.content_rw}".lower()
        if query and query not in haystack:
            continue
        filtered.append(article_view(article, language, include_content=False))
    return filtered


@router.get("/knowledge/articles/{slug}")
def get_knowledge_article(
    slug: str,
    language: str = Query(default="en", pattern="^(en|rw)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(current_user),
):
    seed_knowledge(db)
    article = db.scalar(
        select(KnowledgeArticle).where(KnowledgeArticle.slug == slug).options(selectinload(KnowledgeArticle.sources))
    )
    if not article:
        raise HTTPException(status_code=404, detail="Knowledge article not found")
    return article_view(article, language)


@router.get("/knowledge/conversations")
def list_knowledge_conversations(db: Session = Depends(get_db), user: User = Depends(current_user)):
    conversations = db.scalars(
        select(KnowledgeConversation)
        .where(KnowledgeConversation.owner_id == user.id)
        .order_by(KnowledgeConversation.updated_at.desc())
    ).all()
    return [{
        "id": item.id, "title": item.title, "language": item.language,
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
    } for item in conversations]


@router.get("/knowledge/conversations/{conversation_id}")
def get_knowledge_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    conversation = db.scalar(
        select(KnowledgeConversation)
        .where(KnowledgeConversation.id == conversation_id, KnowledgeConversation.owner_id == user.id)
        .options(selectinload(KnowledgeConversation.messages).selectinload(KnowledgeMessage.retrievals))
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_view(conversation)


@router.post("/knowledge/ask")
def ask_knowledge(payload: KnowledgeQuestion, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        result = answer_question(db, user.id, payload.question, payload.language, payload.conversation_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.add(AuditLog(user_id=user.id, action="ask", entity_type="knowledge_conversation", entity_id=result["conversation_id"]))
    db.commit()
    return result

