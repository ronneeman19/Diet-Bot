"""Daily PNG report generator using Pillow."""
from __future__ import annotations

import io
import logging
from datetime import date
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

from app.models import Message, Food
from app.services.firebase_db import firebase_db
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

_CANVAS_SIZE = (600, 800)
_BG_COLOR = (255, 255, 255)
_TEXT_COLOR = (0, 0, 0)
_BAR_COLORS = {
    "protein": (52, 152, 219),  # blue
    "carbs": (46, 204, 113),    # green
    "fat": (231, 76, 60),       # red
}
_MARGIN = 40


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:  # pragma: no cover
        return ImageFont.load_default()


def _aggregate(messages: list[Message]) -> Tuple[float, dict[str, float]]:
    total_cal = 0.0
    macros = {"protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for m in messages:
        for food in m.food:
            total_cal += food.calories
            macros["protein"] += food.macros.protein_g
            macros["carbs"] += food.macros.carbs_g
            macros["fat"] += food.macros.fat_g
    return total_cal, macros


def _draw_bar_chart(draw: ImageDraw.Draw, macros: dict[str, float], top_y: int) -> None:
    bar_width = 100
    spacing = 40
    max_height = 200
    max_val = max(macros.values()) or 1
    x = _MARGIN
    font = _load_font(20)
    for name, val in macros.items():
        height = int((val / max_val) * max_height)
        y0 = top_y + (max_height - height)
        y1 = top_y + max_height
        draw.rectangle([x, y0, x + bar_width, y1], fill=_BAR_COLORS[name])
        draw.text((x, y1 + 5), name.capitalize(), font=font, fill=_TEXT_COLOR)
        draw.text((x, y0 - 20), f"{val:.0f}g", font=font, fill=_TEXT_COLOR)
        x += bar_width + spacing


def generate_png_report(user_id: str, target_date: date) -> str:
    msgs = firebase_db.fetch_messages_by_date(user_id, target_date)
    total_cal, macros = _aggregate(msgs)

    profile = firebase_db.get_profile(user_id)
    budget = profile.calorie_budget if profile and profile.calorie_budget else 0
    remaining = budget - total_cal if budget else 0

    # Create image
    img = Image.new("RGB", _CANVAS_SIZE, _BG_COLOR)
    draw = ImageDraw.Draw(img)
    title_font = _load_font(32)
    body_font = _load_font(24)

    draw.text((_MARGIN, _MARGIN), f"Daily Recap – {target_date.isoformat()}", font=title_font, fill=_TEXT_COLOR)

    y_cursor = _MARGIN + 60
    draw.text((_MARGIN, y_cursor), f"Total Consumed: {total_cal:.0f} kcal", font=body_font, fill=_TEXT_COLOR)
    y_cursor += 40
    if budget:
        draw.text((_MARGIN, y_cursor), f"Budget: {budget} kcal | Remaining: {remaining:.0f} kcal", font=body_font, fill=_TEXT_COLOR)
    else:
        draw.text((_MARGIN, y_cursor), "No budget set.", font=body_font, fill=_TEXT_COLOR)

    # Bar chart
    _draw_bar_chart(draw, macros, top_y=y_cursor + 60)

    # Footer
    draw.text((_MARGIN, _CANVAS_SIZE[1] - 40), "Keep up the great work!", font=body_font, fill=_TEXT_COLOR)

    # Save to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    # Upload
    filename = f"report_{target_date.isoformat()}"
    gs_path, url = storage_service.upload_image(
        png_bytes,
        user_id,
        filename,
        content_type="image/png",
        compress=False,
    )
    logger.info("Uploaded daily report for %s to %s", user_id, gs_path)
    return url 