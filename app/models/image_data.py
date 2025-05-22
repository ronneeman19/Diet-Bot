from __future__ import annotations

from pydantic import BaseModel, Field


class ImageData(BaseModel):
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    mime_type: str
    resolution: str | None = None  # e.g., "1024x768"
    url: str  # Signed or public GCS URL 