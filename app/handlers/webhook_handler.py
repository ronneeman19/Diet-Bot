"""Webhook handler for Meta WhatsApp Cloud API."""
from __future__ import annotations

import hmac
import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.config import get_settings
from app.services.whatsapp import whatsapp_client
from app.services.firebase_db import firebase_db
from app.services.storage import storage_service
from app.models import Message, ImageData
from app.services.agent import AgentRunner

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def verify_signature(body: bytes, signature_header: str | None) -> None:
    if signature_header is None:
        raise HTTPException(status_code=403, detail="Missing signature header")
    expected = hmac.new(
        key=settings.whatsapp_app_secret.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    try:
        algo, received = signature_header.split("=", 1)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Bad signature header") from exc
    if algo != "sha256" or not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=403, detail="Invalid signature")


# ---------------------------------------------------------------------------
# Verification GET
# ---------------------------------------------------------------------------


@router.get("/webhook")
async def verify_webhook(mode: str, challenge: str, verify_token: str):  # noqa: D401
    """Meta webhook verification endpoint."""
    if mode == "subscribe" and verify_token == settings.whatsapp_verify_token:
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


# ---------------------------------------------------------------------------
# POST webhook
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
):
    raw_body = await request.body()
    verify_signature(raw_body, x_hub_signature_256)

    payload = await request.json()
    logger.debug("Webhook payload: %s", payload)

    # Extract message info
    try:
        entry = payload["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages", [])
        if not messages:
            return {"status": "ignored"}
        msg = messages[0]
        from_phone = msg["from"]
    except (KeyError, IndexError) as exc:
        logger.error("Malformed webhook payload: %s", exc)
        raise HTTPException(status_code=400, detail="Bad payload")

    if from_phone != settings.primary_user_phone:
        logger.warning("Unknown sender: %s", from_phone)
        return {"status": "ignored"}

    user_id = "primary"
    message_id = msg.get("id", "")
    timestamp = datetime.utcnow()

    # Handle message types
    if msg["type"] == "text":
        text_body = msg["text"]["body"]
        m = Message(
            id=message_id,
            user_id=user_id,
            timestamp=timestamp,
            role="user",
            type="text",
            content=text_body,
        )
        firebase_db.add_message(user_id, m)
        background_tasks.add_task(run_agent, user_id, text_body)
    elif msg["type"] == "image":
        media_id = msg["image"]["id"]
        media_bytes, content_type = await whatsapp_client.download_media(media_id)
        gs_path, url = storage_service.upload_image(media_bytes, user_id, message_id, content_type=content_type)
        img_data = ImageData(width=0, height=0, mime_type=content_type, url=url)
        m = Message(
            id=message_id,
            user_id=user_id,
            timestamp=timestamp,
            role="user",
            type="image",
            content="(image)",
            gcs_path=gs_path,
            image_data=img_data,
        )
        firebase_db.add_message(user_id, m)
        background_tasks.add_task(run_agent, user_id, url)
    else:
        logger.info("Unsupported message type: %s", msg["type"])

    return {"status": "received"}


def run_agent(user_id: str, incoming: str) -> None:
    try:
        AgentRunner(user_id).run(incoming)
    except Exception as exc:  # pragma: no cover
        logger.exception("Agent run failed: %s", exc) 