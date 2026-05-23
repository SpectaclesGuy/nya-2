from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.database import connect_to_mongo, disconnect_from_mongo, get_db
from app.utils.email import normalize_email


async def main() -> None:
    email = normalize_email(settings.initial_admin_email)
    name = (settings.initial_admin_name or "").strip()

    if not settings.mongodb_uri:
        raise SystemExit("Set MONGODB_URI in .env before creating the first admin.")
    if not email or "@" not in email:
        raise SystemExit("Set INITIAL_ADMIN_EMAIL (a valid email) in .env.")
    if not name:
        raise SystemExit("Set INITIAL_ADMIN_NAME in .env.")

    await connect_to_mongo()
    try:
        db = get_db()
        existing_admin = await db["users"].find_one({"role": "admin"})
        if existing_admin:
            print("Admin already exists; not creating a new one.")
            return

        now = datetime.utcnow()
        doc = {
            "google_sub": None,
            "name": name,
            "login_email": email,
            "phone_number": None,
            "alternate_email": None,
            "avatar_url": None,
            "role": "admin",
            "profile_completed": True,
            "is_active": True,
            "created_by_admin_id": None,
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        }
        await db["users"].insert_one(doc)
        print(f"Created first admin: {email}")
        print("Login via /auth/google/login using the exact same Google email.")
    finally:
        await disconnect_from_mongo()


if __name__ == "__main__":
    asyncio.run(main())
