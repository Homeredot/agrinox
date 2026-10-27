from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    preferred_language: Mapped[str] = mapped_column(String(2), default="en")
    phone: Mapped[str | None] = mapped_column(String(30))
    location: Mapped[str | None] = mapped_column(String(160))
    bio: Mapped[str | None] = mapped_column(String(500))
    avatar_kind: Mapped[str] = mapped_column(String(12), default="vector")
    avatar_key: Mapped[str] = mapped_column(String(30), default="farmer")
    avatar_color: Mapped[str] = mapped_column(String(20), default="forest")
    profile_image_path: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    two_factor_method: Mapped[str | None] = mapped_column(String(20))
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    two_factor_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    farms: Mapped[list["Farm"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    knowledge_conversations: Mapped[list["KnowledgeConversation"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    crop_plans: Mapped[list["CropPlan"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    plant_lens_cases: Mapped[list["PlantLensCase"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    satellite_areas: Mapped[list["SatelliteArea"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    calendar_tasks: Mapped[list["CalendarTask"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    financial_plans: Mapped[list["FinancialPlan"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    financial_transactions: Mapped[list["FinancialTransaction"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    notification_preference: Mapped["NotificationPreference | None"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    app_notifications: Mapped[list["AppNotification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    email_deliveries: Mapped[list["EmailDelivery"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    two_factor_challenges: Mapped[list["TwoFactorChallenge"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def has_profile_photo(self) -> bool:
        return bool(self.profile_image_path)


class TwoFactorChallenge(Base):
    __tablename__ = "two_factor_challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(30), index=True)
    method: Mapped[str] = mapped_column(String(20))
    code_hash: Mapped[str | None] = mapped_column(String(64))
    pending_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship(back_populates="two_factor_challenges")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    calendar_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    irrigation_events: Mapped[bool] = mapped_column(Boolean, default=True)
    device_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    soil_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    plant_results: Mapped[bool] = mapped_column(Boolean, default=True)
    planning_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    finance_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    security_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    user: Mapped[User] = relationship(back_populates="notification_preference")


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"
    __table_args__ = (
        Index("ix_email_deliveries_user_created", "user_id", "created_at"),
        Index("ix_email_deliveries_category_created", "category", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    event_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(30), index=True)
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="email_deliveries")


class AppNotification(Base):
    __tablename__ = "app_notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_app_notifications_user_event"),
        Index("ix_app_notifications_user_created", "user_id", "created_at"),
        Index("ix_app_notifications_user_read", "user_id", "is_read"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    event_key: Mapped[str] = mapped_column(String(180))
    title: Mapped[str] = mapped_column(String(240))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="app_notifications")


class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    province: Mapped[str] = mapped_column(String(100))
    district: Mapped[str] = mapped_column(String(100))
    sector: Mapped[str] = mapped_column(String(100))
    cell: Mapped[str] = mapped_column(String(100))
    village: Mapped[str] = mapped_column(String(100))
    province_code: Mapped[int | None] = mapped_column(ForeignKey("provinces.code", ondelete="RESTRICT"))
    district_code: Mapped[int | None] = mapped_column(ForeignKey("districts.code", ondelete="RESTRICT"))
    sector_code: Mapped[str | None] = mapped_column(ForeignKey("sectors.code", ondelete="RESTRICT"))
    cell_code: Mapped[int | None] = mapped_column(ForeignKey("cells.code", ondelete="RESTRICT"))
    village_code: Mapped[int | None] = mapped_column(ForeignKey("villages.code", ondelete="RESTRICT"), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    owner: Mapped[User] = relationship(back_populates="farms")
    fields: Mapped[list["FarmField"]] = relationship(back_populates="farm", cascade="all, delete-orphan")


class FarmField(Base):
    __tablename__ = "farm_fields"
    __table_args__ = (CheckConstraint("area_m2 > 0", name="ck_field_area_positive"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    crop_note: Mapped[str | None] = mapped_column(String(120))
    side_a_m: Mapped[float | None] = mapped_column(Float)
    side_b_m: Mapped[float | None] = mapped_column(Float)
    side_c_m: Mapped[float | None] = mapped_column(Float)
    side_d_m: Mapped[float | None] = mapped_column(Float)
    area_m2: Mapped[float] = mapped_column(Float)
    area_source: Mapped[str] = mapped_column(String(20))
    boundary_geojson: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    farm: Mapped[Farm] = relationship(back_populates="fields")
    devices: Mapped[list["Device"]] = relationship(back_populates="field")
    soil_readings: Mapped[list["SoilReading"]] = relationship(back_populates="field", cascade="all, delete-orphan")
    soil_context: Mapped["SoilContext | None"] = relationship(back_populates="field", cascade="all, delete-orphan", uselist=False)
    crop_plans: Mapped[list["CropPlan"]] = relationship(back_populates="field", cascade="all, delete-orphan")
    irrigation_config: Mapped["IrrigationConfig | None"] = relationship(back_populates="field", cascade="all, delete-orphan", uselist=False)
    calendar_tasks: Mapped[list["CalendarTask"]] = relationship(back_populates="field", cascade="all, delete-orphan")
    financial_plans: Mapped[list["FinancialPlan"]] = relationship(back_populates="field", cascade="all, delete-orphan")
    water_sources: Mapped[list["WaterSource"]] = relationship(back_populates="field", cascade="all, delete-orphan")


class CalendarTask(Base):
    __tablename__ = "calendar_tasks"
    __table_args__ = (
        Index("ix_calendar_tasks_owner_due", "owner_id", "due_at"),
        Index("ix_calendar_tasks_field_status", "field_id", "status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("farm_fields.id", ondelete="CASCADE"), index=True)
    crop_plan_id: Mapped[int | None] = mapped_column(ForeignKey("crop_plans.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(String(1000))
    category: Mapped[str] = mapped_column(String(40), index=True)
    crop: Mapped[str | None] = mapped_column(String(80), index=True)
    growth_stage: Mapped[str | None] = mapped_column(String(80))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    recurrence: Mapped[str] = mapped_column(String(20), default="none")
    recurrence_interval: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    email_reminder: Mapped[bool] = mapped_column(Boolean, default=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str] = mapped_column(String(20), default="manual")
    source_title: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    owner: Mapped[User] = relationship(back_populates="calendar_tasks")
    field: Mapped[FarmField] = relationship(back_populates="calendar_tasks")
    crop_plan: Mapped["CropPlan | None"] = relationship(back_populates="calendar_tasks")


class SatelliteArea(Base):
    """A user-saved coordinate AOI. It is not presented as a surveyed field."""

    __tablename__ = "satellite_areas"
    __table_args__ = (Index("ix_satellite_areas_owner_created", "owner_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[float] = mapped_column(Float)
    geometry_geojson: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    owner: Mapped[User] = relationship(back_populates="satellite_areas")


class CropPlan(Base):
    __tablename__ = "crop_plans"
    __table_args__ = (Index("ix_crop_plans_owner_created", "owner_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("farm_fields.id", ondelete="CASCADE"), index=True)
    crop: Mapped[str] = mapped_column(String(80))
    season: Mapped[str] = mapped_column(String(1))
    planned_planting_date: Mapped[date] = mapped_column(Date)
    irrigation: Mapped[str] = mapped_column(String(30))
    previous_crop: Mapped[str | None] = mapped_column(String(80))
    previous_harvest_tonnes: Mapped[float | None] = mapped_column(Float)
    soil_notes: Mapped[str | None] = mapped_column(String(500))
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    owner: Mapped[User] = relationship(back_populates="crop_plans")
    field: Mapped[FarmField] = relationship(back_populates="crop_plans")
    calendar_tasks: Mapped[list[CalendarTask]] = relationship(back_populates="crop_plan")
    financial_plans: Mapped[list["FinancialPlan"]] = relationship(back_populates="crop_plan")


class FinancialPlan(Base):
    __tablename__ = "financial_plans"
    __table_args__ = (Index("ix_financial_plans_owner_created", "owner_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("farm_fields.id", ondelete="CASCADE"), index=True)
    crop_plan_id: Mapped[int | None] = mapped_column(ForeignKey("crop_plans.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    crop: Mapped[str | None] = mapped_column(String(80))
    area_ha: Mapped[float] = mapped_column(Float)
    expected_harvest_kg: Mapped[float] = mapped_column(Float)
    selling_price_per_kg_rwf: Mapped[float] = mapped_column(Float)
    expenses_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    owner: Mapped[User] = relationship(back_populates="financial_plans")
    field: Mapped[FarmField] = relationship(back_populates="financial_plans")
    crop_plan: Mapped[CropPlan | None] = relationship(back_populates="financial_plans")
    transactions: Mapped[list["FinancialTransaction"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"
    __table_args__ = (Index("ix_financial_transactions_plan_date", "plan_id", "occurred_on"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("financial_plans.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(300))
    amount_rwf: Mapped[float] = mapped_column(Float)
    quantity_kg: Mapped[float | None] = mapped_column(Float)
    occurred_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    owner: Mapped[User] = relationship(back_populates="financial_transactions")
    plan: Mapped[FinancialPlan] = relationship(back_populates="transactions")


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (Index("ix_devices_owner_field", "owner_id", "field_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("farm_fields.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    device_uid: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    board: Mapped[str] = mapped_column(String(80), default="ESP32")
    port: Mapped[str] = mapped_column(String(120))
    baud_rate: Mapped[int] = mapped_column(Integer, default=115200)
    firmware_version: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="registered")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    api_key_hash: Mapped[str | None] = mapped_column(String(64))
    remote_control_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    field: Mapped[FarmField | None] = relationship(back_populates="devices")
    sensors: Mapped[list["Sensor"]] = relationship(back_populates="device", cascade="all, delete-orphan")


class Sensor(Base):
    __tablename__ = "sensors"
    __table_args__ = (Index("ix_sensors_device_key", "device_id", "sensor_key", unique=True),)
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    sensor_key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    sensor_type: Mapped[str] = mapped_column(String(80))
    unit: Mapped[str | None] = mapped_column(String(30))
    pin: Mapped[str | None] = mapped_column(String(30))
    latest_value: Mapped[float | None] = mapped_column(Float)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    device: Mapped[Device] = relationship(back_populates="sensors")
    readings: Mapped[list["SensorReading"]] = relationship(back_populates="sensor", cascade="all, delete-orphan")
    water_source: Mapped["WaterSource | None"] = relationship(back_populates="sensor", uselist=False)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (Index("ix_sensor_readings_sensor_time", "sensor_id", "recorded_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id", ondelete="CASCADE"), index=True)
    value: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    valid: Mapped[bool] = mapped_column(Boolean, default=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    sensor: Mapped[Sensor] = relationship(back_populates="readings")


class WaterSource(Base):
    __tablename__ = "water_sources"
    __table_args__ = (
        Index("ix_water_sources_field_primary", "field_id", "is_primary"),
        CheckConstraint("capacity_liters IS NULL OR capacity_liters > 0", name="ck_water_source_capacity_positive"),
        CheckConstraint("tank_height_cm IS NULL OR tank_height_cm > 0", name="ck_water_source_height_positive"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("farm_fields.id", ondelete="CASCADE"), index=True)
    sensor_id: Mapped[int | None] = mapped_column(ForeignKey("sensors.id", ondelete="SET NULL"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(30), index=True)
    capacity_liters: Mapped[float | None] = mapped_column(Float)
    tank_height_cm: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    field: Mapped[FarmField] = relationship(back_populates="water_sources")
    sensor: Mapped[Sensor | None] = relationship(back_populates="water_source")


class IrrigationConfig(Base):
    __tablename__ = "irrigation_configs"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("farm_fields.id", ondelete="CASCADE"), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), default="advisory")
    safety_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    remote_control_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    max_pump_runtime_seconds: Mapped[int] = mapped_column(Integer, default=600)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=15)
    min_tank_percent: Mapped[float] = mapped_column(Float, default=15.0)
    max_reading_age_minutes: Mapped[int] = mapped_column(Integer, default=30)
    moisture_trigger_percent: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    field: Mapped[FarmField] = relationship(back_populates="irrigation_config")


class IrrigationCommand(Base):
    __tablename__ = "irrigation_commands"
    __table_args__ = (Index("ix_irrigation_commands_field_time", "field_id", "issued_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("farm_fields.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    command: Mapped[str] = mapped_column(String(30))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    source: Mapped[str] = mapped_column(String(30), default="manual")
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    reason_json: Mapped[str] = mapped_column(Text)
    execution_message: Mapped[str | None] = mapped_column(String(500))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlantLensCase(Base):
    __tablename__ = "plant_lens_cases"
    __table_args__ = (Index("ix_plant_lens_owner_created", "owner_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    crop_id: Mapped[str] = mapped_column(String(80), index=True)
    image_path: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    prediction_json: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(120))
    confidence: Mapped[float | None] = mapped_column(Float)
    review_status: Mapped[str] = mapped_column(String(40), default="pending_expert", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner: Mapped[User] = relationship(back_populates="plant_lens_cases")


class SoilContext(Base):
    __tablename__ = "soil_contexts"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("farm_fields.id", ondelete="CASCADE"), unique=True, index=True)
    crop_type: Mapped[str | None] = mapped_column(String(80))
    growth_stage: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    field: Mapped[FarmField] = relationship(back_populates="soil_context")


class SoilReading(Base):
    __tablename__ = "soil_readings"
    __table_args__ = (Index("ix_soil_readings_field_type_time", "field_id", "measurement_type", "measured_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("farm_fields.id", ondelete="CASCADE"), index=True)
    measurement_type: Mapped[str] = mapped_column(String(30))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(20))
    calibration_status: Mapped[str] = mapped_column(String(30), default="unknown")
    reliability: Mapped[str] = mapped_column(String(30), default="needs_review")
    note: Mapped[str | None] = mapped_column(String(500))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    field: Mapped[FarmField] = relationship(back_populates="soil_readings")


class GeocodeCache(Base):
    __tablename__ = "geocode_cache"
    id: Mapped[int] = mapped_column(primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(80), unique=True)
    provider: Mapped[str] = mapped_column(String(30), default="nominatim")
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WeatherCache(Base):
    __tablename__ = "weather_cache"
    id: Mapped[int] = mapped_column(primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(30), default="open-meteo")
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Province(Base):
    __tablename__ = "provinces"
    code: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)


class District(Base):
    __tablename__ = "districts"
    code: Mapped[int] = mapped_column(primary_key=True)
    province_code: Mapped[int] = mapped_column(ForeignKey("provinces.code", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(80))


class Sector(Base):
    __tablename__ = "sectors"
    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    district_code: Mapped[int] = mapped_column(ForeignKey("districts.code", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(80))


class Cell(Base):
    __tablename__ = "cells"
    code: Mapped[int] = mapped_column(primary_key=True)
    sector_code: Mapped[str] = mapped_column(ForeignKey("sectors.code", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(80))


class Village(Base):
    __tablename__ = "villages"
    code: Mapped[int] = mapped_column(primary_key=True)
    cell_code: Mapped[int] = mapped_column(ForeignKey("cells.code", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(100))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_user_id_created", "user_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    title_en: Mapped[str] = mapped_column(String(240))
    title_rw: Mapped[str] = mapped_column(String(240))
    content_en: Mapped[str] = mapped_column(Text)
    content_rw: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), index=True)
    author: Mapped[str] = mapped_column(String(180))
    reviewer: Mapped[str] = mapped_column(String(180))
    review_status: Mapped[str] = mapped_column(String(40), index=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sources: Mapped[list["KnowledgeSource"]] = relationship(back_populates="article", cascade="all, delete-orphan")


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("knowledge_articles.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    publisher: Mapped[str] = mapped_column(String(180))
    url: Mapped[str] = mapped_column(String(1000))
    published_date: Mapped[str | None] = mapped_column(String(40))
    article: Mapped[KnowledgeArticle] = relationship(back_populates="sources")


class KnowledgeConversation(Base):
    __tablename__ = "knowledge_conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    language: Mapped[str] = mapped_column(String(2), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, index=True)
    owner: Mapped[User] = relationship(back_populates="knowledge_conversations")
    messages: Mapped[list["KnowledgeMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class KnowledgeMessage(Base):
    __tablename__ = "knowledge_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("knowledge_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    response_mode: Mapped[str | None] = mapped_column(String(40))
    model_name: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    conversation: Mapped[KnowledgeConversation] = relationship(back_populates="messages")
    retrievals: Mapped[list["KnowledgeRetrieval"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class KnowledgeRetrieval(Base):
    __tablename__ = "knowledge_retrievals"
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("knowledge_messages.id", ondelete="CASCADE"), index=True)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_articles.id", ondelete="SET NULL"), index=True)
    query: Mapped[str] = mapped_column(String(1000))
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    article_title: Mapped[str] = mapped_column(String(240))
    source_url: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    message: Mapped[KnowledgeMessage] = relationship(back_populates="retrievals")
    article: Mapped[KnowledgeArticle | None] = relationship()

