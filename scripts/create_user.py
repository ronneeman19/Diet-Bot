#!/usr/bin/env python
"""Script to create the initial user profile in Firebase Realtime DB."""
from __future__ import annotations

import argparse
from pathlib import Path

from app.services.firebase_db import firebase_db
from app.models import UserProfile


def main() -> None:
    parser = argparse.ArgumentParser(description="Create DietBot user profile")
    parser.add_argument("--user_id", default="primary")
    parser.add_argument("--phone_number", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--age", type=int, required=True)
    parser.add_argument("--height_cm", type=float, required=True)
    parser.add_argument("--weight_kg", type=float, required=True)
    parser.add_argument("--goal_weight_kg", type=float, required=True)
    parser.add_argument("--activity_level", default="sedentary")
    parser.add_argument("--timezone", type=int, default=0)
    args = parser.parse_args()

    profile = UserProfile(
        user_id=args.user_id,
        phone_number=args.phone_number,
        name=args.name,
        age=args.age,
        height_cm=args.height_cm,
        weight_kg=args.weight_kg,
        goal_weight_kg=args.goal_weight_kg,
        activity_level=args.activity_level,
        timezone=args.timezone,
    )
    firebase_db.set_profile(profile)
    print("Created user profile:")
    print(profile.model_dump_json(indent=2))


if __name__ == "__main__":
    main() 