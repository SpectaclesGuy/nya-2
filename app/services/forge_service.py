from __future__ import annotations

from app.core.database import get_db


class ForgeService:
    @staticmethod
    async def list_active_forges(limit: int = 24) -> list[dict]:
        db = get_db()
        cursor = (
            db["forges"]
            .find({"is_active": True})
            .sort([("sort_order", 1), ("updated_at", -1)])
            .limit(limit)
        )
        return [doc async for doc in cursor]
