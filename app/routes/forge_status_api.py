from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import StreamingResponse

from app.schemas.forge_status import ForgeStatusOut
from app.services.forge_status_service import ForgeStatusService

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/forge-status", response_model=ForgeStatusOut)
async def get_forge_status() -> ForgeStatusOut:
    try:
        doc = await ForgeStatusService.get_status()
    except RuntimeError:
        return ForgeStatusOut(available=False)

    if not doc:
        return ForgeStatusOut(available=False)

    return ForgeStatusOut.model_validate(doc | {"available": True})


def _sse(data: dict) -> str:
    def default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        return str(o)

    payload = json.dumps(data, ensure_ascii=False, default=default)
    return f"event: forge_status\ndata: {payload}\n\n"


@router.get("/events/forge-status")
async def forge_status_events(request: Request) -> StreamingResponse:
    async def event_gen():
        # Send initial snapshot.
        try:
            doc = await ForgeStatusService.get_status()
        except RuntimeError:
            doc = None
        initial = ForgeStatusOut(available=False) if not doc else ForgeStatusOut.model_validate(doc | {"available": True})
        yield _sse(initial.model_dump())

        # Keepalive + change stream updates.
        keepalive_s = 20
        while True:
            if await request.is_disconnected():
                return
            try:
                async with ForgeStatusService.watch_status_changes() as changes:
                    while True:
                        if await request.is_disconnected():
                            return
                        try:
                            change = await asyncio.wait_for(changes.__anext__(), timeout=keepalive_s)
                        except asyncio.TimeoutError:
                            # Comment keepalive (ignored by EventSource but keeps proxies happy).
                            yield ": keepalive\n\n"
                            continue
                        except StopAsyncIteration:
                            break

                        # On any relevant change, re-fetch and emit canonical snapshot.
                        doc = await ForgeStatusService.get_status()
                        if not doc:
                            yield _sse(ForgeStatusOut(available=False).model_dump())
                        else:
                            yield _sse(ForgeStatusOut.model_validate(doc | {"available": True}).model_dump())
            except Exception:
                # If change streams aren't available (or DB not connected), keep SSE alive with keepalives.
                # This prevents the client from switching to polling.
                while True:
                    if await request.is_disconnected():
                        return
                    yield ": keepalive\n\n"
                    await asyncio.sleep(keepalive_s)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
