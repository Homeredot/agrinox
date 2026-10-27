from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./agrinox.db"
    jwt_secret: str = "development-only-change-me"
    access_token_expire_minutes: int = 1440
    nominatim_user_agent: str = "Agrinox/0.1 (local-development)"
    frontend_origin: str = "http://localhost:3000"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = "gemini-3.6-flash"
    plant_lens_model_path: str = "models/plant_lens_potato_v2.pkl"
    plant_lens_model_version: str = "fastai-potato-plantvillage-v2"
    plant_lens_tomato_model_path: str = "models/plant_lens_tomato_v4.pkl"
    plant_lens_tomato_model_version: str = "fastai-tomato-plantvillage-v4"
    plant_lens_max_upload_mb: int = 10
    planet_client_id: str | None = None
    planet_client_secret: str | None = None
    planet_sentinel_base_url: str = "https://services.sentinel-hub.com"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    email_enabled: bool = False
    email_host: str | None = Field(default=None, validation_alias=AliasChoices("EMAIL_HOST", "SMTP_HOST"))
    email_port: int = Field(default=587, validation_alias=AliasChoices("EMAIL_PORT", "SMTP_PORT"))
    email_user: str | None = Field(default=None, validation_alias=AliasChoices("EMAIL_USER", "SMTP_USERNAME"))
    email_pass: str | None = Field(default=None, validation_alias=AliasChoices("EMAIL_PASS", "SMTP_PASSWORD"))
    email_from: str | None = Field(default=None, validation_alias=AliasChoices("EMAIL_FROM", "SMTP_FROM_EMAIL", "EMAIL_USER", "SMTP_USERNAME"))
    email_use_tls: bool = Field(default=True, validation_alias=AliasChoices("EMAIL_USE_TLS", "SMTP_USE_TLS"))
    email_poll_seconds: int = Field(default=60, ge=30, le=3600)
    email_verification_required: bool = True
    device_api_base_url: str | None = None
    device_offline_after_seconds: int = Field(default=180, ge=30, le=3600)
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")


settings = Settings()

