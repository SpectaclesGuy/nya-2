from __future__ import annotations

from typing import Any

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse


class AuthRequired(Exception):
    pass


def get_session_user(request: Request) -> dict[str, Any] | None:
    user = request.session.get("user")
    return user if isinstance(user, dict) else None


def require_user(request: Request) -> dict[str, Any]:
    user = get_session_user(request)
    if not user:
        raise AuthRequired()
    return user


def require_role(role: str):
    def _dep(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
        if user.get("role") != role:
            raise AuthRequired()
        return user

    return _dep


async def auth_exception_handler(request: Request, exc: AuthRequired):
    return RedirectResponse("/", status_code=302)
