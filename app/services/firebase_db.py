"""Firebase Realtime Database helper utilities.

This module wraps common CRUD operations for user profiles and chat
messages stored under the following path structure:

/users/{user_id}/profile
/users/{user_id}/messages/{message_id}

All data is validated with Pydantic models before being written or
returned. Callers may request the results as models or raw dictionaries
(using the ``as_dict`` keyword).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, date
from typing import Literal, Any, List

import firebase_admin
from firebase_admin import credentials, db

from app.config import get_settings
from app.models import UserProfile, Message

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Initialise the Firebase Admin SDK exactly once.
# ---------------------------------------------------------------------------

if not firebase_admin._apps:  # type: ignore[attr-defined]
    try:
        if settings.firebase_credentials_json:
            # Accept path or JSON string
            cred_obj: credentials.Base = (
                credentials.Certificate(settings.firebase_credentials_json)
                if settings.firebase_credentials_json.endswith(".json")
                else credentials.Certificate(json.loads(settings.firebase_credentials_json))
            )
        else:
            # Attempt default credentials (useful on Cloud Run with workload identity)
            cred_obj = credentials.ApplicationDefault()

        firebase_admin.initialize_app(
            cred_obj,
            {
                "databaseURL": f"https://{settings.project_id}.firebaseio.com"
                if settings.project_id
                else None,
            },
        )
        logger.info("Firebase Admin SDK initialised.")
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to initialise Firebase Admin SDK: %s", exc)
        raise

# ---------------------------------------------------------------------------
# Helper class
# ---------------------------------------------------------------------------


def _validate_message_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise a raw message dict.

    Returns the validated JSON-ready dict.
    """

    msg = Message.model_validate(data)
    return msg.model_dump(mode="json")


def _validate_profile_dict(data: dict[str, Any]) -> dict[str, Any]:
    profile = UserProfile.model_validate(data)
    return profile.model_dump(mode="json")


class FirebaseDB:  # pylint: disable=too-few-public-methods
    """Wrapper around Firebase Realtime Database operations."""

    def __init__(self) -> None:
        self._root = db.reference("/")

    # -------------------------------------------------------------------
    # User Profile
    # -------------------------------------------------------------------

    def get_profile(self, user_id: str, *, as_dict: bool = False) -> UserProfile | dict | None:
        ref = self._root.child("users").child(user_id).child("profile")
        data = ref.get()
        if data is None:
            return None
        validated = _validate_profile_dict(data)
        return validated if as_dict else UserProfile.model_validate(validated)

    def set_profile(self, profile: UserProfile | dict[str, Any]) -> None:
        if isinstance(profile, UserProfile):
            data = profile.model_dump(mode="json")
            user_id = profile.user_id
        else:
            # Validate first
            data = _validate_profile_dict(profile)
            user_id = data["user_id"]

        ref = self._root.child("users").child(user_id).child("profile")
        ref.set(data)
        logger.debug("Profile set for user_id=%s", user_id)

    # -------------------------------------------------------------------
    # Messages
    # -------------------------------------------------------------------

    def _messages_ref(self, user_id: str):
        return self._root.child("users").child(user_id).child("messages")

    def add_message(self, user_id: str, message: Message | dict[str, Any]) -> str:
        if isinstance(message, Message):
            data = message.model_dump(mode="json")
        else:
            data = _validate_message_dict(message)

        # push() returns a reference with a generated key
        push_ref = self._messages_ref(user_id).push()
        data["id"] = push_ref.key  # Store the generated ID inside the document
        push_ref.set(data)
        logger.debug("Added message id=%s to user_id=%s", push_ref.key, user_id)
        return push_ref.key  # type: ignore[return-value]

    def get_message(self, user_id: str, message_id: str, *, as_dict: bool = False) -> Message | dict | None:
        data = self._messages_ref(user_id).child(message_id).get()
        if data is None:
            return None
        validated = _validate_message_dict(data)
        return validated if as_dict else Message.model_validate(validated)

    def fetch_recent_messages(
        self, user_id: str, limit: int = 20, *, as_dict: bool = False
    ) -> List[Message] | List[dict]:
        query = self._messages_ref(user_id).order_by_child("timestamp").limit_to_last(limit)
        raw_items = query.get() or {}
        # raw_items is a dict keyed by message_id -> data
        messages = list(raw_items.values())
        messages.sort(key=lambda m: m["timestamp"], reverse=True)
        validated = [_validate_message_dict(item) for item in messages]
        if as_dict:
            return validated
        return [Message.model_validate(v) for v in validated]

    def fetch_messages_by_date(
        self, user_id: str, target_date: date, *, as_dict: bool = False
    ) -> List[Message] | List[dict]:
        start_ts = datetime.combine(target_date, datetime.min.time())
        end_ts = datetime.combine(target_date, datetime.max.time())
        return self.query_messages(
            user_id,
            start_ts=start_ts,
            end_ts=end_ts,
            as_dict=as_dict,
        )

    def query_messages(
        self,
        user_id: str,
        *,
        start_ts: datetime | None = None,
        end_ts: datetime | None = None,
        role: Literal["user", "ai"] | None = None,
        msg_type: Literal["text", "image"] | None = None,
        limit: int = 100,
        as_dict: bool = False,
    ) -> List[Message] | List[dict]:
        query = self._messages_ref(user_id).order_by_child("timestamp")
        if start_ts is not None:
            query = query.start_at(start_ts.isoformat())
        if end_ts is not None:
            query = query.end_at(end_ts.isoformat())
        query = query.limit_to_last(limit)

        raw_items = query.get() or {}
        items: list[dict[str, Any]] = list(raw_items.values())

        # In-Python filtering for role/type
        if role is not None:
            items = [i for i in items if i.get("role") == role]
        if msg_type is not None:
            items = [i for i in items if i.get("type") == msg_type]

        # Sort newest first
        items.sort(key=lambda m: m["timestamp"], reverse=True)

        validated = [_validate_message_dict(i) for i in items]
        if as_dict:
            return validated
        return [Message.model_validate(v) for v in validated]


# Instantiate a singleton for app-wide reuse
firebase_db = FirebaseDB() 