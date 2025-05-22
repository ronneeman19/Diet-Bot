from __future__ import annotations

from pydantic import BaseModel, Field


class Schedule(BaseModel):
    morning_checkin: str = Field("07:00", regex=r"^\d{2}:\d{2}$")
    daily_recap: str = Field("21:00", regex=r"^\d{2}:\d{2}$")


class UserProfile(BaseModel):
    user_id: str
    phone_number: str
    name: str
    age: int
    height_cm: float
    weight_kg: float
    goal_weight_kg: float
    activity_level: str
    timezone: int = 0  # UTC offset, e.g., 0, 1, -5
    schedule: Schedule = Schedule()
    calorie_budget: int | None = None 