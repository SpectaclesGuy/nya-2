from __future__ import annotations

from datetime import datetime

from pymongo import ReturnDocument

from app.core.database import get_db
from app.models.user import UserInDb
from app.utils.email import normalize_email


class UserService:
    @staticmethod
    async def find_by_login_email(login_email: str) -> dict | None:
        db = get_db()
        return await db["users"].find_one({"login_email": normalize_email(login_email)})

    @staticmethod
    async def find_admin_by_email(login_email: str) -> dict | None:
        db = get_db()
        return await db["users"].find_one(
            {"login_email": normalize_email(login_email), "role": "admin", "is_active": True}
        )

    @staticmethod
    async def upsert_google_user(
        *,
        google_sub: str,
        login_email: str,
        name: str | None,
        avatar_url: str | None,
        role: str,
    ) -> dict:
        db = get_db()
        now = datetime.utcnow()
        base = UserInDb(
            google_sub=google_sub,
            login_email=normalize_email(login_email),
            name=name,
            avatar_url=avatar_url,
            role=role,  # type: ignore[arg-type]
            profile_completed=(role == "admin"),
            is_active=True,
            last_login_at=now,
            updated_at=now,
        ).model_dump()

        # Do not allow role escalation via login.
        update = {
            "$setOnInsert": {
                "created_at": now,
                "role": role,
                "profile_completed": base["profile_completed"],
                "is_active": True,
            },
            "$set": {
                "google_sub": google_sub,
                "login_email": base["login_email"],
                "name": name,
                "avatar_url": avatar_url,
                "updated_at": now,
                "last_login_at": now,
            },
        }
        doc = await db["users"].find_one_and_update(
            {"login_email": base["login_email"]},
            update,
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return doc

    @staticmethod
    async def upsert_candidate_profile(
        *, login_email: str, data: dict, profile_completed: bool = True
    ) -> dict:
        db = get_db()
        now = datetime.utcnow()
        set_data = dict(data or {})
        # Canonical fields.
        if "alternate_email" in set_data and set_data["alternate_email"]:
            set_data["alternate_email"] = normalize_email(str(set_data["alternate_email"]))
        # Always treat these as lists when present.
        if "skills" in set_data and set_data["skills"] is None:
            set_data["skills"] = []
        if "other_links" in set_data and set_data["other_links"] is None:
            set_data["other_links"] = []

        doc = await db["users"].find_one_and_update(
            {"login_email": normalize_email(login_email), "role": "candidate"},
            {
                "$set": {
                    **set_data,
                    "profile_completed": bool(profile_completed),
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            raise RuntimeError("User not found")
        return doc

    @staticmethod
    async def set_profile_completed(*, login_email: str, completed: bool) -> dict | None:
        db = get_db()
        now = datetime.utcnow()
        return await db["users"].find_one_and_update(
            {"login_email": normalize_email(login_email)},
            {"$set": {"profile_completed": bool(completed), "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
