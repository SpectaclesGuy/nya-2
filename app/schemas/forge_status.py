from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ForgeStatusOut(BaseModel):
    available: bool = False
    status: str | None = Field(default=None, max_length=24)
    heat_percent: int | None = Field(default=None, ge=0, le=100)
    heat_label: str | None = Field(default=None, max_length=24)
    pod_tracks_active: int | None = Field(default=None, ge=0, le=10_000)
    seats_left: int | None = Field(default=None, ge=0, le=10_000)
    total_users: int | None = Field(default=None, ge=0, le=10_000_000)
    total_submissions: int | None = Field(default=None, ge=0, le=10_000_000)
    updated_at: datetime | None = None
