from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .food import Food
from .image_data import ImageData
from .llm_parameters import LLMParameters


class Message(BaseModel):
    """Represents a single chat turn, user or AI."""

    id: str
    user_id: str
    timestamp: datetime
    role: Literal["user", "ai"]
    type: Literal["text", "image"]
    content: str
    gcs_path: str | None = None
    image_data: ImageData | None = None
    food: list[Food] = []
    llm_parameters: LLMParameters | None = None 