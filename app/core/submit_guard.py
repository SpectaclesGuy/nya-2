from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager


def _get_limit() -> int:
    raw = os.getenv("SUBMIT_CONCURRENCY", "4").strip()
    try:
        limit = int(raw)
    except Exception:
        limit = 4
    return max(0, limit)


_LIMIT = _get_limit()
_SEMAPHORE: asyncio.Semaphore | None = asyncio.Semaphore(_LIMIT) if _LIMIT > 0 else None


@asynccontextmanager
async def submit_slot(*, timeout_s: float = 2.0):
    """
    Caps concurrent "submit" handlers per worker to keep tiny instances stable.
    Set SUBMIT_CONCURRENCY=0 to disable.
    """

    if _SEMAPHORE is None:
        yield
        return

    try:
        await asyncio.wait_for(_SEMAPHORE.acquire(), timeout=timeout_s)
    except TimeoutError as e:
        raise RuntimeError("busy") from e
    try:
        yield
    finally:
        _SEMAPHORE.release()

