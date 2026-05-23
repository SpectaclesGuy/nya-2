from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import connect_to_mongo, disconnect_from_mongo, get_db


DEFAULT_FORGES = [
    {
        "forge_id": "NYA-F01",
        "name": "FindMe",
        "badge_text": "CRITICAL",
        "badge_tone": "primary",
        "heat_level": "MAX",
        "open_seats_text": "01/12",
        "output": "Consumer App",
        "access_state": "request_access",
        "sort_order": 1,
        "is_active": True,
    },
    {
        "forge_id": "NYA-F02",
        "name": "EvalTrust",
        "badge_text": "WARM",
        "badge_tone": "secondary",
        "heat_level": "STEADY",
        "open_seats_text": "03/10",
        "output": "Audit Engine",
        "access_state": "request_access",
        "sort_order": 2,
        "is_active": True,
    },
    {
        "forge_id": "NYA-F03",
        "name": "Research Div",
        "badge_text": None,
        "badge_tone": "outline",
        "heat_level": "INTENSE",
        "open_seats_text": "LOCKED",
        "output": "Whitepaper",
        "access_state": "waitlist_only",
        "sort_order": 3,
        "is_active": True,
    },
    {
        "forge_id": "NYA-F04",
        "name": "Hackathon Engine",
        "badge_text": None,
        "badge_tone": "outline",
        "heat_level": "BURST",
        "open_seats_text": "08/20",
        "output": "48hr Sprints",
        "access_state": "request_access",
        "sort_order": 4,
        "is_active": True,
    },
    {
        "forge_id": "NYA-F05",
        "name": "Internal Tools",
        "badge_text": None,
        "badge_tone": "outline",
        "heat_level": "LOW",
        "open_seats_text": "05/15",
        "output": "NYA Systems",
        "access_state": "request_access",
        "sort_order": 5,
        "is_active": True,
    },
    {
        "forge_id": "NYA-F06",
        "name": "Client Systems",
        "badge_text": None,
        "badge_tone": "outline",
        "heat_level": "HIGH",
        "open_seats_text": "02/06",
        "output": "Real Deployment",
        "access_state": "request_access",
        "sort_order": 6,
        "is_active": True,
    },
]


async def main() -> None:
    if not settings.mongodb_uri:
        raise SystemExit("Set MONGODB_URI in .env before seeding.")
    await connect_to_mongo()
    try:
        db = get_db()
        now = datetime.now(tz=timezone.utc)
        for f in DEFAULT_FORGES:
            f = dict(f)
            f["updated_at"] = now
            await db["forges"].update_one({"forge_id": f["forge_id"]}, {"$set": f}, upsert=True)
        print("Seeded forges:", len(DEFAULT_FORGES))
    finally:
        await disconnect_from_mongo()


if __name__ == "__main__":
    asyncio.run(main())

