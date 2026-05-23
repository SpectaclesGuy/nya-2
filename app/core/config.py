from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NYA Job Portal"
    environment: str = "development"

    secret_key: str = "change-me"
    session_secret_key: str = "change-me-too"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    mongodb_uri: str = ""
    mongodb_db_name: str = "nya_portal"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    allowed_institution_domains: str = ""

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "NYA Job Portal"

    allowed_origins: str = ""

    initial_admin_email: str = ""
    initial_admin_name: str = ""

    max_resume_size_mb: int = 5

    # Dev-only helpers (do not enable in production)
    dev_login_enabled: bool = False
    dev_login_token: str = ""

    @property
    def cookie_secure_effective(self) -> bool:
        return self.cookie_secure or self.environment.lower() == "production"

    @property
    def allowed_domains_list(self) -> list[str]:
        raw = [d.strip().lower() for d in self.allowed_institution_domains.split(",") if d.strip()]
        return sorted(set(raw))

    @property
    def allowed_origins_list(self) -> list[str]:
        raw = [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        return sorted(set(raw))


settings = Settings()

if settings.environment.lower() == "production":
    if settings.secret_key in {"change-me", "", None} or settings.session_secret_key in {"change-me-too", "", None}:
        raise RuntimeError("Refusing to start in production with default SECRET_KEY/SESSION_SECRET_KEY.")
    if not settings.mongodb_uri:
        raise RuntimeError("Refusing to start in production without MONGODB_URI.")
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError("Refusing to start in production without GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET.")
    if not settings.google_redirect_uri:
        raise RuntimeError("Refusing to start in production without GOOGLE_REDIRECT_URI.")

# Dev-login guardrails (avoid accidental enablement).
if settings.dev_login_enabled and not settings.dev_login_token:
    raise RuntimeError("DEV_LOGIN_ENABLED=true requires DEV_LOGIN_TOKEN to be set.")
