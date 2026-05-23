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
        keepalive_s = 20
        refresh_s = 15

        # Send initial snapshot.
        try:
            doc = await ForgeStatusService.get_status()
        except RuntimeError:
            doc = None
        initial = ForgeStatusOut(available=False) if not doc else ForgeStatusOut.model_validate(doc | {"available": True})
        yield _sse(initial.model_dump())

        # "Real-time enough": push periodic snapshots to avoid client polling.
        # If change streams work, we'll emit immediately on forge_status updates too.
        next_refresh = asyncio.get_event_loop().time() + refresh_s
        last_payload: str | None = None

        while True:
            if await request.is_disconnected():
                return

            now = asyncio.get_event_loop().time()
            timeout = max(0.1, min(keepalive_s, next_refresh - now))

            got_change = False
            try:
                async with ForgeStatusService.watch_status_changes() as changes:
                    try:
                        await asyncio.wait_for(changes.__anext__(), timeout=timeout)
                        got_change = True
                    except asyncio.TimeoutError:
                        got_change = False
                    except StopAsyncIteration:
                        got_change = False
            except Exception:
                # Change streams not available; fall back to timed refresh only.
                got_change = False

            # keepalive (ignored by EventSource but keeps proxies happy).
            yield ": keepalive\n\n"

            now = asyncio.get_event_loop().time()
            if got_change or now >= next_refresh:
                next_refresh = now + refresh_s
                try:
                    doc = await ForgeStatusService.get_status()
                except RuntimeError:
                    doc = None

                out = ForgeStatusOut(available=False) if not doc else ForgeStatusOut.model_validate(doc | {"available": True})
                payload = _sse(out.model_dump())
                # Avoid spamming identical snapshots.
                if payload != last_payload:
                    yield payload
                    last_payload = payload

    return StreamingResponse(event_gen(), media_type="text/event-stream")
