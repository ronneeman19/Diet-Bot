"""Google Cloud Storage helper for Diet-Bot.

Responsible for uploading user images, optional compression, and URL
retrieval.  Objects are stored under the following key pattern:

    users/{user_id}/{message_id}.{ext}

Callers receive both the *gs://* path and an externally accessible URL
(signed or public depending on configuration).
"""
from __future__ import annotations

import io
import logging
import os
from datetime import timedelta
from typing import Tuple

from google.cloud import storage
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class StorageService:  # pylint: disable=too-few-public-methods
    """Wrapper around Google Cloud Storage uploads and signed URLs."""

    _VALID_IMAGE_PREFIX = "image/"
    _MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

    def __init__(self) -> None:
        self._client = storage.Client()
        self._bucket = self._client.bucket(settings.bucket_name)
        if not self._bucket.exists():  # pragma: no cover
            logger.warning("GCS bucket '%s' does not exist or access denied.", settings.bucket_name)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def upload_image(
        self,
        file_bytes: bytes,
        user_id: str,
        message_id: str,
        *,
        content_type: str,
        compress: bool = True,
        expires: timedelta = timedelta(days=7),
    ) -> Tuple[str, str]:
        """Upload an image and return (gs_path, url).

        Parameters
        ----------
        file_bytes : bytes
            Raw image bytes as received from WhatsApp.
        user_id : str
            ID of the user owning the image.
        message_id : str
            Associated message ID.
        content_type : str
            Mime type, must start with ``image/``.
        compress : bool, optional
            If *True* (default) the image will be resized/compressed to
            ``settings.image_max_dim`` and ``settings.image_quality``.
        expires : timedelta, optional
            Signed URL expiry (ignored if PUBLIC_IMAGES=true).
        """

        if not content_type.startswith(self._VALID_IMAGE_PREFIX):
            raise ValueError("Unsupported content_type; expected image/*, got %s" % content_type)

        if len(file_bytes) > self._MAX_UPLOAD_BYTES:
            raise ValueError("Image exceeds 10 MB size limit.")

        ext = _content_type_to_extension(content_type)
        blob_name = f"users/{user_id}/{message_id}.{ext}"
        blob = self._bucket.blob(blob_name)

        data_to_upload = file_bytes
        final_content_type = content_type

        if compress:
            try:
                data_to_upload, final_content_type = _compress_image(
                    file_bytes,
                    content_type,
                    max_dim=settings.image_max_dim,
                    quality=settings.image_quality,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Image compression failed, uploading original bytes: %s", exc)

        blob.upload_from_string(data_to_upload, content_type=final_content_type)

        if settings.public_images:
            try:
                blob.make_public()
                url = blob.public_url
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to make blob public: %s", exc)
                url = blob.generate_signed_url(expires)
        else:
            url = blob.generate_signed_url(expires)

        gs_path = f"gs://{settings.bucket_name}/{blob_name}"
        logger.debug("Uploaded image to %s", gs_path)
        return gs_path, url

    def get_signed_url(
        self,
        user_id: str,
        message_id: str,
        *,
        expires: timedelta = timedelta(days=7),
    ) -> str:
        ext_candidates = ["jpg", "jpeg", "png", "webp"]
        for ext in ext_candidates:
            blob = self._bucket.blob(f"users/{user_id}/{message_id}.{ext}")
            if blob.exists():
                return blob.generate_signed_url(expires)
        raise FileNotFoundError("Image blob not found for message_id=%s" % message_id)

    def delete_image(self, user_id: str, message_id: str) -> None:
        for ext in ("jpg", "jpeg", "png", "webp"):
            blob = self._bucket.blob(f"users/{user_id}/{message_id}.{ext}")
            if blob.exists():
                blob.delete()
                logger.debug("Deleted image blob %s", blob.name)


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------

def _content_type_to_extension(content_type: str) -> str:
    mapping = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    return mapping.get(content_type.lower(), "jpg")


def _compress_image(
    file_bytes: bytes,
    content_type: str,
    *,
    max_dim: int,
    quality: int,
) -> Tuple[bytes, str]:
    """Resize/compress image bytes using Pillow and return (bytes, new_content_type)."""

    with Image.open(io.BytesIO(file_bytes)) as img:
        img = img.convert("RGB")  # ensure RGB for JPEG
        # Resize preserving aspect ratio if necessary
        width, height = img.size
        if max(width, height) > max_dim:
            img.thumbnail((max_dim, max_dim))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        return buffer.getvalue(), "image/jpeg"


# Singleton instance
storage_service = StorageService() 