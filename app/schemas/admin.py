from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AdminUserRow(BaseModel):
    id: str = Field(alias="_id")
    login_email: str
    name: str | None = None
    role: str
    profile_completed: bool = False
    is_active: bool = True
    last_login_at: datetime | None = None


class AdminJobUpsert(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    company_or_team: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=120)
    job_type: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=6000)
    deadline: str | None = None  # ISO date or empty; parsed in route for simplicity

