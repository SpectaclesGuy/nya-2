from __future__ import annotations

from datetime import datetime

from pymongo import ReturnDocument

from app.core.database import get_db
from app.models.track_questionnaire import TrackQuestionnaireInDb


class TrackQuestionnaireService:
    @staticmethod
    async def get_by_section(*, section: str) -> dict | None:
        if section not in {"project_internship", "research_internship"}:
            return None
        db = get_db()
        return await db["track_questionnaires"].find_one({"section": section})

    @staticmethod
    async def upsert_for_section(*, section: str, items: list[dict]) -> dict:
        if section not in {"project_internship", "research_internship"}:
            raise RuntimeError("Invalid section")
        db = get_db()
        now = datetime.utcnow()
        base = TrackQuestionnaireInDb(section=section, items=items, created_at=now, updated_at=now).model_dump()
        update = {
            "$setOnInsert": {"created_at": now, "section": section},
            "$set": {"items": base["items"], "updated_at": now},
        }
        doc = await db["track_questionnaires"].find_one_and_update(
            {"section": section},
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return doc

    @staticmethod
    async def list_all(*, limit: int = 100) -> list[dict]:
        db = get_db()
        cursor = db["track_questionnaires"].find({}).sort([("updated_at", -1)]).limit(limit)
        return [doc async for doc in cursor]
