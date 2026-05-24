from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class JobPublicOut(BaseModel):
    id: str = Field(validation_alias="_id")
    type: str | None = Field(default=None, max_length=32)
    title: str
    company_or_team: str
    location: str
    job_type: str
    updated_at: datetime | None = None
