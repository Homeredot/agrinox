from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    preferred_language: Literal["en", "rw"] = "en"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LanguageUpdate(BaseModel):
    preferred_language: Literal["en", "rw"]


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    location: str | None = Field(default=None, max_length=160)
    bio: str | None = Field(default=None, max_length=500)
    avatar_key: Literal["farmer", "sprout", "leaf", "wheat", "mountain", "sun"] | None = None
    avatar_color: Literal["forest", "moss", "earth", "sunrise", "sky", "plum"] | None = None

    @model_validator(mode="after")
    def has_a_change(self):
        if not self.model_fields_set:
            raise ValueError("Provide profile information to update")
        return self


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class TwoFactorSetupRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


class TwoFactorCodeRequest(BaseModel):
    challenge_token: str = Field(min_length=20, max_length=200)
    code: str = Field(pattern=r"^\d{6}$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str
    preferred_language: str
    phone: str | None = None
    location: str | None = None
    bio: str | None = None
    avatar_kind: str
    avatar_key: str
    avatar_color: str
    has_profile_photo: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class NotificationPreferenceUpdate(BaseModel):
    enabled: bool | None = None
    calendar_reminders: bool | None = None
    irrigation_events: bool | None = None
    device_alerts: bool | None = None
    soil_alerts: bool | None = None
    plant_results: bool | None = None
    planning_updates: bool | None = None
    finance_updates: bool | None = None
    security_updates: bool | None = None


class FarmCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    province: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=100)
    sector: str = Field(min_length=2, max_length=100)
    cell: str = Field(min_length=2, max_length=100)
    village: str = Field(min_length=2, max_length=100)
    province_code: int
    district_code: int
    sector_code: str = Field(min_length=6, max_length=12)
    cell_code: int
    village_code: int
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinates_are_paired(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together")
        return self


class FieldCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    crop_note: str | None = Field(default=None, max_length=120)
    side_a: float | None = Field(default=None, gt=0)
    side_b: float | None = Field(default=None, gt=0)
    side_c: float | None = Field(default=None, gt=0)
    side_d: float | None = Field(default=None, gt=0)
    side_unit: Literal["cm", "m", "km"] = "m"
    boundary_geojson: dict | None = None

    @model_validator(mode="after")
    def has_area_input(self):
        sides = [self.side_a, self.side_b, self.side_c, self.side_d]
        if self.boundary_geojson is None and not all(value is not None for value in sides):
            raise ValueError("Draw a boundary or provide all four side lengths")
        return self


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    farm_id: int
    name: str
    crop_note: str | None
    side_a_m: float | None
    side_b_m: float | None
    side_c_m: float | None
    side_d_m: float | None
    area_m2: float
    area_source: str
    boundary_geojson: str | None
    created_at: datetime


class WaterSourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    source_type: Literal["tank", "pond", "borehole", "river", "tap", "rainwater", "other"]
    capacity_liters: float | None = Field(default=None, gt=0, le=100_000_000)
    tank_height_cm: float | None = Field(default=None, gt=0, le=100_000)
    sensor_id: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=500)
    is_primary: bool = False

    @model_validator(mode="after")
    def tank_only_measurements(self):
        if self.source_type != "tank" and any(value is not None for value in (self.capacity_liters, self.tank_height_cm, self.sensor_id)):
            raise ValueError("Capacity, tank height and level sensor can only be set for a tank")
        return self


class WaterSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    capacity_liters: float | None = Field(default=None, gt=0, le=100_000_000)
    tank_height_cm: float | None = Field(default=None, gt=0, le=100_000)
    sensor_id: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=500)
    is_primary: bool | None = None
    is_active: bool | None = None


class FarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    province: str
    district: str
    sector: str
    cell: str
    village: str
    province_code: int | None
    district_code: int | None
    sector_code: str | None
    cell_code: int | None
    village_code: int | None
    latitude: float | None
    longitude: float | None
    created_at: datetime
    fields: list[FieldOut] = []


class SatelliteMonitorRequest(BaseModel):
    field_id: int | None = Field(default=None, ge=1)
    latitude: float | None = Field(default=None, ge=-2.9, le=-1.0)
    longitude: float | None = Field(default=None, ge=28.8, le=30.9)
    radius_m: float = Field(default=250, ge=50, le=2000)
    label: str | None = Field(default=None, max_length=160)
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def has_one_area(self):
        has_field = self.field_id is not None
        has_point = self.latitude is not None and self.longitude is not None
        if has_field == has_point:
            raise ValueError("Choose one mapped field or one searched location")
        if self.date_to < self.date_from:
            raise ValueError("End date must be after the start date")
        if (self.date_to - self.date_from).days > 730:
            raise ValueError("Satellite history is limited to two years per request")
        return self


class SatelliteAreaCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    latitude: float = Field(ge=-2.9, le=-1.0)
    longitude: float = Field(ge=28.8, le=30.9)
    radius_m: float = Field(default=250, ge=50, le=2000)


class DiscoveredSensor(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=80)
    unit: str | None = Field(default=None, max_length=30)
    pin: str | None = Field(default=None, max_length=30)


class DeviceCreate(BaseModel):
    field_id: int
    name: str = Field(min_length=2, max_length=120)
    device_uid: str = Field(min_length=2, max_length=120)
    port: str = Field(min_length=1, max_length=120)
    board: str = Field(default="ESP32", max_length=80)
    baud_rate: int = Field(default=115200, ge=1200, le=2000000)
    firmware_version: str | None = Field(default=None, max_length=80)
    sensors: list[DiscoveredSensor] = Field(default_factory=list, max_length=64)


class FirmwareInstallRequest(BaseModel):
    port: str = Field(min_length=3, max_length=120)
    wifi_ssid: str = Field(min_length=1, max_length=32)
    wifi_password: SecretStr = Field(min_length=8, max_length=63)


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    field_id: int | None = None


class IoTReadingInput(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    value: float
    unit: str | None = Field(default=None, max_length=30)
    recorded_at: datetime | None = None
    valid: bool = True
    simulated: bool = False


class IoTReadingBatch(BaseModel):
    firmware_version: str | None = Field(default=None, max_length=80)
    sent_at: datetime | None = None
    readings: list[IoTReadingInput] = Field(min_length=1, max_length=64)


class IoTHeartbeat(BaseModel):
    firmware_version: str | None = Field(default=None, max_length=80)
    wifi_rssi: int | None = Field(default=None, ge=-120, le=0)
    ip_address: str | None = Field(default=None, max_length=45)


class IrrigationConfigUpdate(BaseModel):
    mode: Literal["manual", "advisory", "automatic"] = "advisory"
    safety_validated: bool = False
    remote_control_enabled: bool = False
    emergency_stop: bool = False
    max_pump_runtime_seconds: int = Field(default=600, ge=10, le=7200)
    cooldown_minutes: int = Field(default=15, ge=1, le=1440)
    min_tank_percent: float = Field(default=15, ge=1, le=90)
    max_reading_age_minutes: int = Field(default=30, ge=1, le=1440)
    moisture_trigger_percent: float | None = Field(default=None, ge=1, le=99)


class IrrigationCommandCreate(BaseModel):
    field_id: int = Field(ge=1)
    command: Literal["start", "stop", "emergency_stop"]
    duration_seconds: int | None = Field(default=None, ge=1, le=7200)
    simulated: bool = False


class DeviceCommandStatus(BaseModel):
    status: Literal["executed", "completed", "failed", "rejected"]
    message: str | None = Field(default=None, max_length=500)


class PlantLensReviewUpdate(BaseModel):
    review_status: Literal["farmer_reviewed", "pending_expert", "dismissed"]


class SoilMeasurementInput(BaseModel):
    measurement_type: Literal["nitrogen", "phosphorus", "potassium", "moisture", "temperature", "ph"]
    value: float
    unit: str = Field(min_length=1, max_length=30)
    calibration_status: Literal["calibrated", "uncalibrated", "not_applicable", "unknown"] = "unknown"
    reliability: Literal["reliable", "needs_review", "unreliable"] = "needs_review"


class SoilReadingCreate(BaseModel):
    source: Literal["manual", "laboratory"]
    measured_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)
    measurements: list[SoilMeasurementInput] = Field(min_length=1, max_length=6)


class SoilContextUpdate(BaseModel):
    crop_type: str | None = Field(default=None, max_length=80)
    growth_stage: str | None = Field(default=None, max_length=80)


class KnowledgeQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    language: Literal["en", "rw"] = "en"
    conversation_id: int | None = Field(default=None, ge=1)


class CropPlanCreate(BaseModel):
    field_id: int = Field(ge=1)
    crop: str = Field(min_length=2, max_length=80)
    season: Literal["A", "B", "C"]
    planned_planting_date: date
    irrigation: Literal["available", "rainfed", "limited", "unknown"] = "unknown"
    previous_crop: str | None = Field(default=None, max_length=80)
    previous_harvest_tonnes: float | None = Field(default=None, ge=0)
    soil_notes: str | None = Field(default=None, max_length=500)


class CropRecommendationRequest(BaseModel):
    field_id: int = Field(ge=1)
    season: Literal["A", "B", "C"]
    planned_planting_date: date


CalendarCategory = Literal["soil_preparation", "planting", "fertilizer_assessment", "irrigation", "pest_scouting", "field_maintenance", "harvesting", "post_harvest"]
CalendarRecurrence = Literal["none", "daily", "weekly", "monthly"]


class CalendarTaskCreate(BaseModel):
    field_id: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=1000)
    category: CalendarCategory
    crop: str | None = Field(default=None, max_length=80)
    growth_stage: str | None = Field(default=None, max_length=80)
    due_at: datetime
    reminder_at: datetime | None = None
    recurrence: CalendarRecurrence = "none"
    recurrence_interval: int = Field(default=1, ge=1, le=52)
    email_reminder: bool = True
    source_type: Literal["manual", "suggested"] = "manual"
    source_title: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def reminder_precedes_due_date(self):
        if self.reminder_at is not None and self.reminder_at > self.due_at:
            raise ValueError("Reminder must be scheduled before the task is due")
        return self


class CalendarTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=1000)
    category: CalendarCategory | None = None
    crop: str | None = Field(default=None, max_length=80)
    growth_stage: str | None = Field(default=None, max_length=80)
    due_at: datetime | None = None
    reminder_at: datetime | None = None
    recurrence: CalendarRecurrence | None = None
    recurrence_interval: int | None = Field(default=None, ge=1, le=52)
    email_reminder: bool | None = None


class CalendarSuggestionRequest(BaseModel):
    field_id: int = Field(ge=1)
    crop: str = Field(min_length=2, max_length=80)
    planting_date: date
    growth_stage: str | None = Field(default=None, max_length=80)


ExpenseCategory = Literal["seeds", "fertilizer", "labor", "transport", "irrigation", "equipment", "land_preparation", "pest_management", "other"]


class PlannedExpenseInput(BaseModel):
    category: ExpenseCategory
    description: str | None = Field(default=None, max_length=300)
    amount_rwf: float = Field(ge=0, le=10_000_000_000)


class FinancialCalculationRequest(BaseModel):
    area_ha: float = Field(gt=0, le=100_000)
    expected_harvest_kg: float = Field(gt=0, le=10_000_000_000)
    selling_price_per_kg_rwf: float = Field(ge=0, le=100_000_000)
    expenses: list[PlannedExpenseInput] = Field(default_factory=list, max_length=100)


class FinancialPlanCreate(FinancialCalculationRequest):
    field_id: int = Field(ge=1)
    crop_plan_id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=2, max_length=180)
    crop: str | None = Field(default=None, max_length=80)


class FinancialPlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    crop: str | None = Field(default=None, max_length=80)
    area_ha: float | None = Field(default=None, gt=0, le=100_000)
    expected_harvest_kg: float | None = Field(default=None, gt=0, le=10_000_000_000)
    selling_price_per_kg_rwf: float | None = Field(default=None, ge=0, le=100_000_000)
    expenses: list[PlannedExpenseInput] | None = Field(default=None, max_length=100)


class FinancialTransactionCreate(BaseModel):
    kind: Literal["expense", "revenue"]
    category: ExpenseCategory | Literal["crop_sale", "other_income"]
    description: str = Field(min_length=2, max_length=300)
    amount_rwf: float = Field(gt=0, le=10_000_000_000)
    quantity_kg: float | None = Field(default=None, gt=0, le=10_000_000_000)
    occurred_on: date

    @model_validator(mode="after")
    def category_matches_kind(self):
        revenue_categories = {"crop_sale", "other_income"}
        if self.kind == "revenue" and self.category not in revenue_categories:
            raise ValueError("Revenue must use crop_sale or other_income")
        if self.kind == "expense" and self.category in revenue_categories:
            raise ValueError("Expense must use an expense category")
        return self

