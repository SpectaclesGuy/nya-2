from __future__ import annotations

from datetime import datetime

from pymongo import ReturnDocument

from app.core.database import get_db
from app.models.job import JobInDb
from app.utils.objectid import parse_objectid


class JobService:
    @staticmethod
    async def list_jobs_admin(limit: int = 500) -> list[dict]:
        db = get_db()
        cursor = db["jobs"].find({}).sort([("updated_at", -1)]).limit(limit)
        return [doc async for doc in cursor]

    @staticmethod
    async def list_published_jobs(limit: int = 200) -> list[dict]:
        db = get_db()
        cursor = (
            db["jobs"]
            .find({"status": "published"})
            .sort([("updated_at", -1)])
            .limit(limit)
        )
        return [doc async for doc in cursor]

    @staticmethod
    async def get_job(job_id: str) -> dict | None:
        db = get_db()
        return await db["jobs"].find_one({"_id": parse_objectid(job_id)})

    @staticmethod
    async def get_published_job(job_id: str) -> dict | None:
        db = get_db()
        return await db["jobs"].find_one({"_id": parse_objectid(job_id), "status": "published"})

    @staticmethod
    async def create_job(*, data: dict, created_by: str | None) -> str:
        db = get_db()
        now = datetime.utcnow()
        doc = JobInDb(**data, created_by=created_by, created_at=now, updated_at=now).model_dump()
        res = await db["jobs"].insert_one(doc)
        return str(res.inserted_id)

    @staticmethod
    async def update_job(*, job_id: str, data: dict) -> dict:
        db = get_db()
        now = datetime.utcnow()
        updated = await db["jobs"].find_one_and_update(
            {"_id": parse_objectid(job_id)},
            {"$set": {**data, "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise RuntimeError("Job not found")
        return updated

    @staticmethod
    async def set_status(*, job_id: str, status: str) -> dict:
        if status not in {"draft", "published", "closed"}:
            raise RuntimeError("Invalid status")
        return await JobService.update_job(job_id=job_id, data={"status": status})

    @staticmethod
    async def delete_job(job_id: str) -> None:
        db = get_db()
        await db["jobs"].delete_one({"_id": parse_objectid(job_id)})

    @staticmethod
    async def set_questions(*, job_id: str, questions: list[dict]) -> dict:
        return await JobService.update_job(job_id=job_id, data={"questions": questions})
