from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import BaseSettings, Field

# Load environment variables from a .env file if present (local dev only)
load_dotenv()


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    # General
    project_id: Optional[str] = Field(default=None, description="GCP project ID")

    # OpenAI
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o", env="OPENAI_MODEL")

    # WhatsApp / Meta Cloud API
    whatsapp_token: str = Field(..., env="WHATSAPP_TOKEN")
    whatsapp_phone_id: str = Field(..., env="WHATSAPP_PHONE_ID")
    whatsapp_api_version: str = Field("v19.0", env="WHATSAPP_API_VERSION")
    whatsapp_app_secret: str = Field(..., env="WHATSAPP_APP_SECRET")
    whatsapp_verify_token: str = Field(..., env="WHATSAPP_VERIFY_TOKEN")
    primary_user_phone: str = Field(..., env="PRIMARY_USER_PHONE")

    # Firebase
    firebase_credentials_json: Optional[str] = Field(
        default=None,
        env="GOOGLE_APPLICATION_CREDENTIALS",
        description="Path to service-account JSON file or JSON string itself.",
    )

    # Cloud Storage
    bucket_name: str = Field("dietbot-images", env="BUCKET_NAME")

    # Image processing / storage
    image_max_dim: int = Field(1024, env="IMAGE_MAX_DIM", description="Maximum width or height for uploaded images (pixels).")
    image_quality: int = Field(85, env="IMAGE_QUALITY", description="JPEG/PNG quality for compressed uploads (1-100).")
    public_images: bool = Field(False, env="PUBLIC_IMAGES", description="If true, uploaded images are made public instead of using signed URLs.")

    # Scheduler security
    scheduler_token: str = Field(..., env="SCHEDULER_TOKEN")

    # Defaults
    timezone_default: int = Field(0, description="Default UTC offset, e.g., 0 for UTC.")

    # LLM provider selection & OpenAI params
    llm_provider: str = Field("openai", env="LLM_PROVIDER")
    openai_temperature: float = Field(0.3, env="OPENAI_TEMPERATURE")
    openai_top_p: float = Field(1.0, env="OPENAI_TOP_P")
    openai_max_tokens: int = Field(1024, env="OPENAI_MAX_TOKENS")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:  # pragma: no cover
    """Return a cached Settings instance so it is only parsed once."""

    return Settings() 