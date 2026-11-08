"""
Application configuration using Pydantic Settings.
Loads settings from environment variables or falls back to secure defaults.
"""
from pathlib import Path
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ROOT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    # Application Info
    APP_NAME: str = "KitchenVerse"
    APP_TAGLINE: str = "Multiple Kitchens. One Destination."
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Security & Cryptography
    SECRET_KEY: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        import os

        if os.getenv("APP_ENV", "development") == "production":
            if len(value) < 32:
                raise ValueError(
                    "SECRET_KEY must contain at least 32 characters in production"
                )
            if value == "change-this-to-a-very-secure-random-secret-key-at-least-32-chars":
                raise ValueError("Replace the default SECRET_KEY in production")

        return value
    SESSION_COOKIE_NAME: str = "cloudkitchen_session"
    SESSION_COOKIE_SECURE: bool = False  # set True in HTTPS production
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "lax"
    SESSION_MAX_AGE_SECONDS: int = 86400  # 24 hours

    # CORS
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return self.CORS_ORIGINS

    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/cloudkitchen_db"
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"

    # Machine Learning & Data
    DATA_DIR: str = "./data"
    ML_MODELS_DIR: str = "./ml/artifacts"
    # External Integrations
    PAYMENT_GATEWAY_MODE: str = "unconfigured"  # unconfigured, mock, razorpay, stripe
    PAYMENT_API_KEY: str = ""
    PAYMENT_API_SECRET: str = ""

    # Email / Notifications
    EMAIL_PROVIDER: str = "console"
    EMAIL_FROM: str = "noreply@kitchenverse.com"
    FRONTEND_URL: str = "http://localhost:3000"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "KitchenVerse Support"
    SENDGRID_API_KEY: str = ""

    @property
    def sender_display_name(self) -> str:
        return (self.SMTP_FROM_NAME or "KitchenVerse Support").strip('\"\'')

    @property
    def sender_email_address(self) -> str:
        return self.SMTP_FROM_EMAIL or self.EMAIL_FROM or self.SMTP_USER or ""

    @property
    def smtp_clean_password(self) -> str:
        """Strip enclosing quotes and whitespace (Google App Passwords are shown as 4x4 character blocks with spaces)."""
        return (self.SMTP_PASSWORD or "").strip('\"\'').replace(" ", "")

    model_config = SettingsConfigDict(
        env_file=(
            str(_BACKEND_DIR / ".env"),
            str(_ROOT_DIR / ".env"),
        ),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
