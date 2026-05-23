from __future__ import annotations

import secrets
import hmac
from typing import Any

from fastapi import Request


CSRF_SESSION_KEY = "csrf_token"


def get_csrf_token(session: dict[str, Any]) -> str:
    token = session.get(CSRF_SESSION_KEY)
    if isinstance(token, str) and token:
        return token
    token = secrets.token_urlsafe(32)
    session[CSRF_SESSION_KEY] = token
    return token


async def validate_csrf(request: Request) -> None:
    expected = request.session.get(CSRF_SESSION_KEY)
    provided = request.headers.get("X-CSRF-Token")
    if not provided and request.method.upper() == "POST":
        try:
            form = await request.form()
            provided = form.get("csrf_token")  # type: ignore[assignment]
        except Exception:
            provided = None
    if not expected or not provided:
        raise ValueError("CSRF validation failed")
    if not hmac.compare_digest(str(expected), str(provided)):
        raise ValueError("CSRF validation failed")
