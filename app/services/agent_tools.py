"""Agent tool definitions and executors."""
from __future__ import annotations

import logging
from datetime import datetime, date
from typing import List, Callable, Any

from pydantic import BaseModel, Field

from app.models import Message, Food
from app.services.firebase_db import firebase_db
from app.services.storage import storage_service
from app.utils.calorie_estimator import estimate_fallback
from app.services.llm import chat_completion
from app.services.whatsapp import whatsapp_client
from app.models import UserProfile
from app.reports import report_generator  # placeholder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool: FetchRecentMessages
# ---------------------------------------------------------------------------


class FetchRecentMessagesInput(BaseModel):
    limit: int = Field(20, ge=1, le=100)


class FetchRecentMessagesOutput(BaseModel):
    messages: List[Message]


def fetch_recent_messages_exec(user_id: str, inp: FetchRecentMessagesInput) -> FetchRecentMessagesOutput:
    msgs = firebase_db.fetch_recent_messages(user_id, limit=inp.limit)
    return FetchRecentMessagesOutput(messages=msgs)


# ---------------------------------------------------------------------------
# Tool: EstimateCalories (Vision)
# ---------------------------------------------------------------------------


class EstimateCaloriesInput(BaseModel):
    image_url: str


class EstimateCaloriesOutput(BaseModel):
    food: List[Food]


def estimate_calories_exec(user_id: str, inp: EstimateCaloriesInput) -> EstimateCaloriesOutput:
    """Call LLM vision via chat_completion. Fallback to heuristic."""

    prompt_msg = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Estimate calories and macros for foods in this image. Return JSON."},
                {"type": "image_url", "image_url": {"url": inp.image_url}},
            ],
        }
    ]

    try:
        # Expecting LLM to return JSON matching EstimateCaloriesOutput schema
        response, _ = chat_completion(
            messages=prompt_msg, response_model=EstimateCaloriesOutput
        )
        return response  # already parsed
    except Exception as exc:  # pragma: no cover
        logger.warning("Vision calorie estimation failed: %s", exc)
        food = estimate_fallback(reason=str(exc))
        return EstimateCaloriesOutput(food=food)


# ---------------------------------------------------------------------------
# Tool: ComputeDailyBudget
# ---------------------------------------------------------------------------


class ComputeDailyBudgetOutput(BaseModel):
    calorie_budget: int


def compute_daily_budget_exec(user_id: str) -> ComputeDailyBudgetOutput:
    profile = firebase_db.get_profile(user_id)
    if profile is None:
        raise ValueError("Profile not found for user")
    # Simple Mifflin-St Jeor approximation (placeholder)
    weight = profile.weight_kg
    height = profile.height_cm
    age = profile.age
    bmr = 10 * weight + 6.25 * height - 5 * age + 5  # male assumption
    calorie_budget = int(bmr * 1.2 - 500)  # sedentary minus deficit
    return ComputeDailyBudgetOutput(calorie_budget=calorie_budget)


# ---------------------------------------------------------------------------
# Tool: GenerateDailyReport
# ---------------------------------------------------------------------------


class GenerateDailyReportOutput(BaseModel):
    report_url: str


def generate_daily_report_exec(user_id: str) -> GenerateDailyReportOutput:
    today = date.today()
    # Placeholder: assume function returns path/url
    report_url = report_generator.generate_png_report(user_id, today)
    return GenerateDailyReportOutput(report_url=report_url)


# ---------------------------------------------------------------------------
# Tool: Respond
# ---------------------------------------------------------------------------


class RespondInput(BaseModel):
    response: str


class RespondOutput(BaseModel):
    status: str


def respond_exec(user_id: str, phone_number: str, inp: RespondInput) -> RespondOutput:
    whatsapp_client.send_text(phone_number, inp.response, user_id=user_id)
    return RespondOutput(status="sent")


# ---------------------------------------------------------------------------
# Tool: EndConversation
# ---------------------------------------------------------------------------


class EndConversationOutput(BaseModel):
    status: str = "ended"


def end_conversation_exec(user_id: str) -> EndConversationOutput:  # noqa: ARG001
    return EndConversationOutput()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, tuple[type[BaseModel], Callable[..., Any]]] = {
    "FetchRecentMessages": (FetchRecentMessagesInput, fetch_recent_messages_exec),
    "EstimateCalories": (EstimateCaloriesInput, estimate_calories_exec),
    "ComputeDailyBudget": (None, compute_daily_budget_exec),
    "GenerateDailyReport": (None, generate_daily_report_exec),
    "Respond": (RespondInput, respond_exec),
    "EndConversation": (None, end_conversation_exec),
} 