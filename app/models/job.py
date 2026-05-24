from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


JobStatus = Literal["draft", "published", "closed"]
QuestionType = Literal["text", "single_choice", "multiple_choice"]
PostingType = Literal["project_internship", "research_internship"]


class JobQuestion(BaseModel):
    question_id: str
    title: str
    help_text: str | None = None
    question_type: QuestionType
    required: bool = False
    options: list[str] = Field(default_factory=list)
    order: int = 0


class JobInDb(BaseModel):
    type: PostingType = "project_internship"
    title: str
    company_or_team: str
    location: str
    job_type: str
    description: str
    requirements: str | None = None
    responsibilities: str | None = None
    eligibility: str | None = None
    deadline: datetime | None = None
    status: JobStatus = "draft"
    created_by: str | None = None
    questions: list[JobQuestion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
