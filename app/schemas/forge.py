from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


BadgeTone = Literal["primary", "secondary", "outline"]
AccessState = Literal["request_access", "waitlist_only", "locked"]


class ForgePublicOut(BaseModel):
    forge_id: str = Field(min_length=3, max_length=32)
    name: str = Field(min_length=1, max_length=80)
    badge_text: str | None = Field(default=None, max_length=24)
    badge_tone: BadgeTone = "outline"
    heat_level: str = Field(min_length=1, max_length=24)
    open_seats_text: str = Field(min_length=1, max_length=24)
    output: str = Field(min_length=1, max_length=40)
    access_state: AccessState = "request_access"
    updated_at: datetime | None = None
