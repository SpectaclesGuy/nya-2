from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["candidate", "admin"]


class UserInDb(BaseModel):
    google_sub: str | None = None
    name: str | None = None
    login_email: str
    phone_number: str | None = None
    alternate_email: str | None = None
    avatar_url: str | None = None
    role: Role = "candidate"
    profile_completed: bool = False
    is_active: bool = True
    created_by_admin_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: datetime | None = None
