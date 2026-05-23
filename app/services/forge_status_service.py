from __future__ import annotations

from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from app.core.database import get_db


class ForgeStatusService:
    @staticmethod
    async def compute_portal_status() -> dict:
        """
        Derive a simple 'portal status' snapshot from the DB.

        We intentionally keep the output compatible with `ForgeStatusOut` so the Stitch landing page
        can reuse the existing Forge Status panel without redesigning it.
        """
        db = get_db()
        published_jobs = await db["jobs"].count_documents({"status": "published"})
        total_applications = await db["applications"].count_documents({})

        since = datetime.utcnow() - timedelta(hours=24)
        applications_24h = await db["applications"].count_documents({"created_at": {"$gte": since}})

        heat_percent = min(100, int(round(applications_24h * 2)))  # 50 apps/day ~= 100%
        if published_jobs == 0:
            status = "IDLE"
        else:
            status = "ACTIVE"

        if heat_percent >= 85:
            heat_label = "CRITICAL"
        elif heat_percent >= 60:
            heat_label = "HIGH"
        elif heat_percent >= 30:
            heat_label = "STEADY"
        else:
            heat_label = "LOW"

        return {
            "key": "global",
            "status": status,
            "heat_percent": heat_percent,
            "heat_label": heat_label,
            # Re-map the original fields to portal metrics.
            "pod_tracks_active": int(published_jobs),
            "seats_left": int(total_applications),
            "updated_at": datetime.utcnow(),
        }

    @staticmethod
    async def get_status() -> dict | None:
        db = get_db()
        # Prefer a manually managed status doc if present, else compute from portal state.
        doc = await db["forge_status"].find_one({"key": "global"})
        return doc or await ForgeStatusService.compute_portal_status()

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
