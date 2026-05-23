from __future__ import annotations

from datetime import datetime

from pymongo.errors import DuplicateKeyError

from app.core.database import get_db
from app.models.application import ApplicationInDb
from app.utils.objectid import parse_objectid


class ApplicationService:
    @staticmethod
    async def list_applications(*, job_id: str | None = None, limit: int = 2000) -> list[dict]:
        db = get_db()
        q: dict = {}
        if job_id:
            q["job_id"] = str(parse_objectid(job_id))
        cursor = db["applications"].find(q).sort([("created_at", -1)]).limit(limit)
        return [doc async for doc in cursor]

    @staticmethod
    async def find_by_job_and_user(*, job_id: str, user_id: str) -> dict | None:
        db = get_db()
        return await db["applications"].find_one({"job_id": job_id, "user_id": user_id})

    @staticmethod
    async def create_application(*, data: dict) -> str:
        db = get_db()
        now = datetime.utcnow()
        doc = ApplicationInDb(**data, created_at=now, updated_at=now).model_dump()
        try:
            res = await db["applications"].insert_one(doc)
        except DuplicateKeyError as e:
            raise RuntimeError("Duplicate application") from e
        return str(res.inserted_id)

    @staticmethod
    async def get_application_for_user(*, application_id: str, user_id: str) -> dict | None:
        db = get_db()
        doc = await db["applications"].find_one({"_id": parse_objectid(application_id), "user_id": user_id})
        if doc and doc.get("_id"):
            doc["_id"] = str(doc["_id"])
        return doc

    @staticmethod
    async def list_applications_for_user(*, user_id: str, limit: int = 2000) -> list[dict]:
        db = get_db()
        cursor = db["applications"].find({"user_id": user_id}).sort([("created_at", -1)]).limit(limit)
        out = [doc async for doc in cursor]
        for d in out:
            if d.get("_id"):
                d["_id"] = str(d["_id"])
        return out

    @staticmethod
    async def list_applications_for_job(*, job_id: str, limit: int = 2000) -> list[dict]:
        db = get_db()
        cursor = db["applications"].find({"job_id": job_id}).sort([("created_at", -1)]).limit(limit)
        out = [doc async for doc in cursor]
        for d in out:
            if d.get("_id"):
                d["_id"] = str(d["_id"])
        return out

    @staticmethod
    async def get_application_admin(*, application_id: str) -> dict | None:
        db = get_db()
        doc = await db["applications"].find_one({"_id": parse_objectid(application_id)})
        if doc and doc.get("_id"):
            doc["_id"] = str(doc["_id"])
        return doc
