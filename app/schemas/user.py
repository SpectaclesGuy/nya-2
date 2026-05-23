from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.validators import normalize_phone


class CandidateProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone_number: str
    alternate_email: EmailStr

    @field_validator("phone_number")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)
