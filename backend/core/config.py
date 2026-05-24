"""
Configuration management using Pydantic Settings
"""

from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Backend
    BACKEND_URL: str = "http://localhost:8000"
    BACKEND_RELOAD: bool = True

    # Database
    DATABASE_URL: str = "postgresql://nbfc_user:nbfc_pass@localhost:5432/nbfc_audit_dev"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "your-super-secret-key-change-this-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # File Upload
    MAX_UPLOAD_SIZE_MB: int = 500
    UPLOAD_DIR: str = "/tmp/nbfc_uploads"

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Features
    ENABLE_ANALYTICS: bool = True
    ANALYTICS_TIMEOUT_SECONDS: int = 300

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
