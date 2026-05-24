from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ApplicationStatus = Literal["submitted", "reviewed", "shortlisted", "rejected", "selected"]


class ApplicationAnswer(BaseModel):
    question_id: str
    question_text: str
    question_type: str
    answer: str | list[str]


class ApplicationInDb(BaseModel):
    job_id: str
    user_id: str
    candidate_name: str
    candidate_email: str
    candidate_phone: str
    alternate_email: str
    resume_url: str | None = None
    resume_public_id: str | None = None
    track_section: str | None = None
    questionnaire_items: list[dict] = Field(default_factory=list)
    answers: list[ApplicationAnswer] = Field(default_factory=list)
    status: ApplicationStatus = "submitted"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
