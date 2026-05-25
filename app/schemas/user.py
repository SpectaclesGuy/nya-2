from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.validators import normalize_phone


class CandidateProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone_number: str
    alternate_email: EmailStr
    current_city: str = Field(min_length=1, max_length=80)
    current_country: str = Field(min_length=1, max_length=80)
    linkedin_url: str = Field(min_length=1, max_length=500)

    date_of_birth: str = Field(min_length=1, max_length=32)
    gender: Literal["female", "male", "non_binary", "prefer_not_to_say"]
    nationality: str = Field(min_length=1, max_length=80)
    address: str = Field(min_length=1, max_length=500)
    postal_code: str = Field(min_length=1, max_length=20)

    university: str = Field(min_length=1, max_length=120)
    degree: str = Field(min_length=1, max_length=120)
    major: str = Field(min_length=1, max_length=120)
    graduation_year: int = Field(ge=1950, le=2100)
    gpa: str = Field(min_length=1, max_length=20)

    experience_level: Literal["student", "intern", "entry", "mid", "senior"]
    years_of_experience: float = Field(ge=0, le=60)
    skills: list[str] = Field(min_length=1, max_length=80)
    experience_summary: str = Field(min_length=1, max_length=2000)

    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)
    other_links: list[str] = Field(min_length=1, max_length=20)

    available_from: str = Field(min_length=1, max_length=32)
    hours_per_week: int = Field(ge=1, le=80)

    @field_validator("phone_number")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("github_url", "portfolio_url", mode="before")
    @classmethod
    def _empty_to_none_strip(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator(
        "current_city",
        "current_country",
        "linkedin_url",
        "date_of_birth",
        "nationality",
        "address",
        "postal_code",
        "university",
        "degree",
        "major",
        "gpa",
        "experience_summary",
        "available_from",
        mode="before",
    )
    @classmethod
    def _strip_required(cls, v):
        return str(v or "").strip()

    @field_validator("skills", "other_links", mode="before")
    @classmethod
    def _clean_list(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",")]
            return [p for p in parts if p]
        if isinstance(v, list):
            out = []
            for item in v:
                s = str(item).strip()
                if s:
                    out.append(s)
            return out
        return v
