from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.forge import ForgePublicOut
from app.services.forge_service import ForgeService

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/forges", response_model=list[ForgePublicOut])
async def list_forges() -> list[ForgePublicOut]:
    try:
        docs = await ForgeService.list_active_forges(limit=24)
    except RuntimeError:
        # Treat "DB not configured/connected yet" as an empty backend dataset.
        docs = []
    return [ForgePublicOut.model_validate(d) for d in docs]
