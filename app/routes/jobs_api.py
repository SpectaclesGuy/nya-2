from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.job_public import JobPublicOut
from app.services.job_service import JobService

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/jobs", response_model=list[JobPublicOut])
async def list_published_jobs() -> list[JobPublicOut]:
    try:
        jobs = await JobService.list_published_jobs(limit=200)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    out: list[JobPublicOut] = []
    for j in jobs:
        if j.get("_id"):
            j["_id"] = str(j["_id"])
        out.append(JobPublicOut.model_validate(j))
    return out

