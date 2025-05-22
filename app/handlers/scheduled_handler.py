"""Scheduled endpoints for daily reminders and recap reports."""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.services.firebase_db import firebase_db
from app.services.whatsapp import whatsapp_client
from app.services.agent_tools import compute_daily_budget_exec, generate_daily_report_exec

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

PRIMARY_USER_ID = "primary"


def _check_token(header_token: str | None):
    if header_token != settings.scheduler_token:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/scheduled/morning_checkin")
async def morning_checkin(scheduler_token: str | None = Header(None, alias="Scheduler-Token")):
    _check_token(scheduler_token)
    profile = firebase_db.get_profile(PRIMARY_USER_ID)
    if profile is None:
        raise HTTPException(status_code=500, detail="Profile not found")

    # Ensure calorie budget exists
    if profile.calorie_budget is None:
        profile.calorie_budget = compute_daily_budget_exec(PRIMARY_USER_ID).calorie_budget
        firebase_db.set_profile(profile)

    msg = (
        f"Good morning, {profile.name}! Your calorie budget for today is "
        f"{profile.calorie_budget} kcal. Stay focused and have a great day!"
    )
    whatsapp_client.send_text(profile.phone_number, msg, user_id=PRIMARY_USER_ID)
    logger.info("Morning check-in sent to %s", profile.phone_number)
    return {"status": "sent"}


@router.get("/scheduled/daily_recap")
async def daily_recap(scheduler_token: str | None = Header(None, alias="Scheduler-Token")):
    _check_token(scheduler_token)
    profile = firebase_db.get_profile(PRIMARY_USER_ID)
    if profile is None:
        raise HTTPException(status_code=500, detail="Profile not found")

    report = generate_daily_report_exec(PRIMARY_USER_ID)
    whatsapp_client.send_image_url(
        profile.phone_number,
        report.report_url,
        caption="Here's your day in review!",
        user_id=PRIMARY_USER_ID,
    )
    logger.info("Daily recap sent to %s", profile.phone_number)
    return {"status": "sent"} 