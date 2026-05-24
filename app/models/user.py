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
    current_city: str | None = None
    current_country: str | None = None
    linkedin_url: str | None = None

    date_of_birth: str | None = None
    gender: str | None = None
    nationality: str | None = None
    address: str | None = None
    postal_code: str | None = None

    university: str | None = None
    degree: str | None = None
    major: str | None = None
    graduation_year: int | None = None
    gpa: str | None = None

    experience_level: str | None = None
    years_of_experience: float | None = None
    skills: list[str] | None = None
    experience_summary: str | None = None

    github_url: str | None = None
    portfolio_url: str | None = None
    other_links: list[str] | None = None

    available_from: str | None = None
    hours_per_week: int | None = None
    work_mode: str | None = None
    relocation_ok: bool | None = None
    notice_period_weeks: int | None = None

    resume_url: str | None = None
    resume_public_id: str | None = None
    resume_updated_at: datetime | None = None
    avatar_url: str | None = None
    role: Role = "candidate"
    profile_completed: bool = False
    is_active: bool = True
    created_by_admin_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: datetime | None = None
