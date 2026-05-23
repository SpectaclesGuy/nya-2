from __future__ import annotations

from contextlib import asynccontextmanager

from app.core.database import get_db


class ForgeStatusService:
    @staticmethod
    async def get_status() -> dict | None:
        db = get_db()
        # Single global status doc.
        return await db["forge_status"].find_one({"key": "global"})

    @staticmethod
    @asynccontextmanager
    async def watch_status_changes():
        db = get_db()
        # Requires MongoDB replica set / Atlas (change streams).
        # Keep pipeline minimal to avoid missing events when fullDocument is absent (e.g., deletes).
        stream = db["forge_status"].watch(full_document="updateLookup")
        try:
            yield stream
        finally:
            await stream.close()
