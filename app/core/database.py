from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None
logger = logging.getLogger(__name__)


async def connect_to_mongo() -> None:
    global _client, _db
    if _client is not None:
        return
    if not settings.mongodb_uri:
        # Allow running without DB for landing page / early dev.
        return
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client[settings.mongodb_db_name]
    try:
        await _db["users"].create_index("login_email", unique=True)
        await _db["users"].create_index("google_sub", unique=True, sparse=True)
        await _db["users"].create_index([("role", 1), ("is_active", 1)])

        await _db["jobs"].create_index("status")
        await _db["jobs"].create_index("type")
        await _db["jobs"].create_index([("status", 1), ("type", 1), ("created_at", -1)])

        await _db["track_questionnaires"].create_index("section", unique=True)

        await _db["applications"].create_index([("job_id", 1), ("user_id", 1)], unique=True)
        await _db["applications"].create_index("job_id")
        await _db["applications"].create_index("user_id")
        await _db["applications"].create_index([("user_id", 1), ("created_at", -1)])
        await _db["applications"].create_index([("job_id", 1), ("created_at", -1)])
        await _db["applications"].create_index([("track_section", 1), ("created_at", -1)])

        await _db["forge_status"].create_index("key", unique=True, sparse=True)
    except Exception:
        # Index creation best-effort (e.g., limited permissions). App still runs.
        logger.exception("MongoDB index creation failed (best-effort)")


async def disconnect_from_mongo() -> None:
    global _client, _db
    if _client is None:
        return
    _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB is not connected. Set MONGODB_URI and restart the app.")
    return _db
