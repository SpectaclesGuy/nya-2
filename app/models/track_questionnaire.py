from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.job import JobQuestion


TrackSection = Literal["project_internship", "research_internship"]


class TrackQuestionnaireInDb(BaseModel):
    section: TrackSection
    items: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
