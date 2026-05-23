from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.csrf import get_csrf_token
from app.core.security import get_session_user

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/me")
async def me(request: Request) -> dict:
    user = get_session_user(request)
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "role": user.get("role"),
        "login_email": user.get("login_email"),
        "profile_completed": bool(user.get("profile_completed")),
        "name": user.get("name"),
    }


@router.get("/csrf")
async def csrf(request: Request) -> dict:
    # Used by static landing page JS to build a safe logout POST.
    return {"csrf_token": get_csrf_token(request.session)}

