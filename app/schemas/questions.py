from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


QuestionType = Literal["text", "single_choice", "multiple_choice"]


class JobQuestionUpsert(BaseModel):
    question_id: str
    title: str = Field(min_length=1, max_length=200)
    help_text: str | None = Field(default=None, max_length=400)
    question_type: QuestionType
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=50)
    order: int = 0

