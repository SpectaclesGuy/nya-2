from __future__ import annotations

from datetime import datetime

from pymongo import ReturnDocument

from app.core.database import get_db
from app.utils.email import normalize_email
from app.utils.objectid import parse_objectid


class AdminService:
    @staticmethod
    async def list_users(limit: int = 500) -> list[dict]:
        db = get_db()
        cursor = db["users"].find({}).sort([("created_at", -1)]).limit(limit)
        return [doc async for doc in cursor]

    @staticmethod
    async def count_admins() -> int:
        db = get_db()
        return await db["users"].count_documents({"role": "admin", "is_active": True})

    @staticmethod
    async def set_role(
        *,
        target_user_id: str,
        new_role: str,
        performed_by_admin_id: str | None,
        performed_by_email: str,
    ) -> dict:
        db = get_db()
        oid = parse_objectid(target_user_id)
        now = datetime.utcnow()
        user = await db["users"].find_one({"_id": oid})
        if not user:
            raise RuntimeError("User not found")

        if new_role not in {"admin", "candidate"}:
            raise RuntimeError("Invalid role")

        # Prevent demoting last active admin.
        if user.get("role") == "admin" and new_role == "candidate":
            admins = await AdminService.count_admins()
            if admins <= 1:
                raise RuntimeError("Cannot demote the last admin")

        updated = await db["users"].find_one_and_update(
            {"_id": oid},
            {"$set": {"role": new_role, "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )

        await db["admin_audit_logs"].insert_one(
            {
                "action": "set_role",
                "performed_by_admin_id": performed_by_admin_id,
                "target_admin_id": str(user.get("_id")),
                "target_email": normalize_email(user.get("login_email", "")),
                "metadata": {"new_role": new_role, "old_role": user.get("role")},
                "created_at": now,
                "performed_by_email": normalize_email(performed_by_email),
            }
        )

        return updated

