"""Fallback calorie estimator utility.

If vision-based calorie estimation fails, we return a single `Food`
object representing 100 g of bread. This prevents downstream logic from
crashing while making it clear that the values are placeholders.
"""
from __future__ import annotations

import logging
from typing import List

from app.models import Food, Macros

logger = logging.getLogger(__name__)


def estimate_fallback(*, reason: str | None = None) -> List[Food]:
    """Return a placeholder food list with a single bread item.

    Parameters
    ----------
    reason : str | None
        Optional description of why the fallback was triggered. Recorded in logs.
    """

    if reason:
        logger.warning("Calorie estimation fallback triggered: %s", reason)
    else:
        logger.warning("Calorie estimation fallback triggered (no reason provided)")

    bread = Food(
        name="Bread",
        estimated_grams=100.0,
        calories=265.0,
        macros=Macros(protein_g=9.0, carbs_g=49.0, fat_g=3.2),
    )
    return [bread] 