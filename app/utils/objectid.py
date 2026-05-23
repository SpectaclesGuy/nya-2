from __future__ import annotations

from bson import ObjectId


def parse_objectid(value: str) -> ObjectId:
    if not value or not ObjectId.is_valid(value):
        raise ValueError("Invalid id")
    return ObjectId(value)

