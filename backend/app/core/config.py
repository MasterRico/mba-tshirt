"""Application configuration (MBA T-Shirt Factory)."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "MBA T-Shirt Factory"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database (standalone MBA DB)
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/mba.db"

    # Auth
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h
    ALGORITHM: str = "HS256"
    # Single shared bearer token guarding /api/v1/*. Set via env. Required in prod.
    API_TOKEN: Optional[str] = None

    # Alerts (optional)
    WEBHOOK_URL: Optional[str] = None
    ALERT_EMAIL: Optional[str] = None

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
