from __future__ import annotations

from pydantic import BaseModel, Field


class Macros(BaseModel):
    protein_g: float = Field(..., ge=0)
    carbs_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)

    class Config:
        arbitrary_types_allowed = True
        orm_mode = True


class Food(BaseModel):
    name: str
    estimated_grams: float = Field(..., ge=0)
    calories: float = Field(..., ge=0)
    macros: Macros 