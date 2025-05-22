"""WhatsApp Business Cloud API wrapper.

Provides async helper methods for sending messages and downloading media.
Only text, image (by URL), and template messages are supported for the MVP.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WhatsAppAPIError(Exception):
    """Raised when the WhatsApp Cloud API returns an error status."""

    def __init__(self, status: int, message: str, response_json: Optional[dict[str, Any]] = None):
        super().__init__(f"WhatsApp API error {status}: {message}")
        self.status = status
        self.response_json = response_json or {}


class WhatsAppClient:  # pylint: disable=too-few-public-methods
    """Minimal async client for Meta WhatsApp Business Cloud API."""

    _BASE_GRAPH_URL = "https://graph.facebook.com"

    def __init__(self, *, token: str, phone_id: str, version: str = "v19.0") -> None:
        self._token = token
        self._phone_id = phone_id
        self._version = version
        self._base_url = f"{self._BASE_GRAPH_URL}/{self._version}"
        self._headers = {"Authorization": f"Bearer {self._token}"}
        self._client = httpx.AsyncClient(timeout=10.0, headers=self._headers)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_text(
        self,
        to: str,
        body: str,
        *,
        preview_url: bool = False,
        log_to_firebase: bool = True,
        user_id: str | None = None,
    ) -> str:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": preview_url},
        }
        message_id = await self._post_message(payload)

        if log_to_firebase and user_id:
            from datetime import datetime  # local import to avoid cycles
            from app.services.firebase_db import firebase_db
            from app.models import Message

            msg = Message(
                id=message_id,
                user_id=user_id,
                timestamp=datetime.utcnow(),
                role="ai",
                type="text",
                content=body,
            )
            firebase_db.add_message(user_id, msg)

        return message_id

    async def send_image_url(
        self,
        to: str,
        image_url: str,
        *,
        caption: str | None = None,
        log_to_firebase: bool = True,
        user_id: str | None = None,
    ) -> str:
        image_obj: Dict[str, Any] = {"link": image_url}
        if caption:
            image_obj["caption"] = caption
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "image",
            "image": image_obj,
        }
        message_id = await self._post_message(payload)

        if log_to_firebase and user_id:
            from datetime import datetime
            from app.services.firebase_db import firebase_db
            from app.models import Message, ImageData

            msg = Message(
                id=message_id,
                user_id=user_id,
                timestamp=datetime.utcnow(),
                role="ai",
                type="image",
                content=caption or "",
                gcs_path=image_url,
            )
            firebase_db.add_message(user_id, msg)

        return message_id

    async def send_template(
        self,
        to: str,
        template_name: str,
        *,
        language_code: str = "en_US",
        components: list[dict[str, Any]] | None = None,
        log_to_firebase: bool = True,
        user_id: str | None = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components
        message_id = await self._post_message(payload)

        if log_to_firebase and user_id:
            from datetime import datetime
            from app.services.firebase_db import firebase_db
            from app.models import Message

            msg = Message(
                id=message_id,
                user_id=user_id,
                timestamp=datetime.utcnow(),
                role="ai",
                type="text",
                content=f"(template:{template_name})",
            )
            firebase_db.add_message(user_id, msg)

        return message_id

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """Download media bytes and return (bytes, content_type)."""

        # Step 1: fetch media metadata to obtain the URL
        meta_url = f"{self._base_url}/{media_id}"
        logger.debug("GET %s", meta_url)
        meta_resp = await self._client.get(meta_url, params={"fields": "url"})
        if meta_resp.status_code >= 400:
            raise WhatsAppAPIError(meta_resp.status_code, meta_resp.text)
        meta_json = meta_resp.json()
        download_url = meta_json.get("url")
        if not download_url:
            raise WhatsAppAPIError(meta_resp.status_code, "Missing download URL in metadata")

        # Step 2: download the binary
        logger.debug("GET media %s", download_url)
        bin_resp = await self._client.get(download_url)
        if bin_resp.status_code >= 400:
            raise WhatsAppAPIError(bin_resp.status_code, "Failed to download media")
        return bin_resp.content, bin_resp.headers.get("Content-Type", "application/octet-stream")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _post_message(self, payload: dict[str, Any]) -> str:
        url = f"{self._base_url}/{self._phone_id}/messages"
        logger.debug("POST %s -> %s", url, payload)
        resp = await self._client.post(url, json=payload)
        if resp.status_code >= 400:
            try:
                err_json = resp.json()
            except ValueError:
                err_json = None
            raise WhatsAppAPIError(resp.status_code, resp.text, err_json)
        data = resp.json()
        message_id = data.get("messages", [{}])[0].get("id")
        return message_id

    async def close(self) -> None:
        await self._client.aclose()


# ------------------------------------------------------------------
# Singleton instance
# ------------------------------------------------------------------

whatsapp_client = WhatsAppClient(
    token=settings.whatsapp_token,
    phone_id=settings.whatsapp_phone_id,
    version=settings.whatsapp_api_version,
) 