from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import connect_to_mongo, disconnect_from_mongo, get_db


async def main() -> None:
    if not settings.mongodb_uri:
        raise SystemExit("Set MONGODB_URI in .env before seeding.")
    await connect_to_mongo()
    try:
        db = get_db()
        now = datetime.now(tz=timezone.utc)
        doc = {
            "key": "global",
            "status": "Active",
            "heat_percent": 94,
            "heat_label": "CRITICAL",
            "pod_tracks_active": 12,
            "seats_left": 4,
            "updated_at": now,
        }
        await db["forge_status"].update_one({"key": "global"}, {"$set": doc}, upsert=True)
        print("Seeded forge status")
    finally:
        await disconnect_from_mongo()


if __name__ == "__main__":
    asyncio.run(main())

