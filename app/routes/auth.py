from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings
from app.core.csrf import validate_csrf
from app.core.rate_limit import limiter
from app.services.user_service import UserService
from app.utils.email import normalize_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _google_auth_url(state: str, nonce: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
        "state": state,
        "nonce": nonce,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


@router.get("/google/login")
@limiter.limit("10/minute")
async def google_login(request: Request):
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _pkce_challenge(code_verifier)
    request.session["oauth_state"] = state
    request.session["oauth_nonce"] = nonce
    request.session["pkce_verifier"] = code_verifier
    url = _google_auth_url(state=state, nonce=nonce)
    url += "&" + urlencode({"code_challenge": code_challenge, "code_challenge_method": "S256"})
    return RedirectResponse(url, status_code=302)


@router.get("/google/callback")
@limiter.limit("10/minute")
async def google_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    expected_state = request.session.pop("oauth_state", None)
    nonce = request.session.pop("oauth_nonce", None)
    code_verifier = request.session.pop("pkce_verifier", None)

    if not code or not state or not expected_state or state != expected_state:
        return RedirectResponse("/", status_code=302)
    if not isinstance(code_verifier, str) or not code_verifier:
        return RedirectResponse("/?error=auth", status_code=302)

    token_endpoint = "https://oauth2.googleapis.com/token"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                token_endpoint,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            token_data = resp.json()
    except Exception:
        return RedirectResponse("/?error=auth", status_code=302)

    raw_id_token = token_data.get("id_token")
    if not raw_id_token:
        return RedirectResponse("/", status_code=302)

    # Verify the ID token server-side (issuer/audience/expiry/signature).
    idinfo = google_id_token.verify_oauth2_token(
        raw_id_token,
        google_requests.Request(),
        settings.google_client_id,
    )

    if idinfo.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        return RedirectResponse("/", status_code=302)

    if not idinfo.get("email_verified"):
        return RedirectResponse("/", status_code=302)

    if nonce and idinfo.get("nonce") and idinfo.get("nonce") != nonce:
        return RedirectResponse("/", status_code=302)

    login_email = normalize_email(idinfo.get("email", ""))
    if not login_email:
        return RedirectResponse("/", status_code=302)

    domain = login_email.split("@")[-1]
    allowed_domains = settings.allowed_domains_list

    role = None
    user_doc = None
    try:
        admin_doc = await UserService.find_admin_by_email(login_email)
        if admin_doc:
            role = "admin"
        else:
            role = "candidate" if domain in allowed_domains else None
        if role:
            user_doc = await UserService.upsert_google_user(
                google_sub=idinfo.get("sub", ""),
                login_email=login_email,
                name=idinfo.get("name"),
                avatar_url=idinfo.get("picture"),
                role=role,
            )
    except RuntimeError:
        # DB not configured yet; enforce domain allowlist at minimum.
        role = "candidate" if domain in allowed_domains else None

    if role is None:
        return RedirectResponse("/?error=unauthorized", status_code=302)

    # Regenerate session after login.
    request.session.clear()
    request.session["user"] = {
        "id": str(user_doc.get("_id")) if isinstance(user_doc, dict) and user_doc.get("_id") else None,
        "google_sub": idinfo.get("sub"),
        "login_email": login_email,
        "name": idinfo.get("name"),
        "avatar_url": idinfo.get("picture"),
        "role": role,
        "profile_completed": bool(user_doc.get("profile_completed")) if isinstance(user_doc, dict) else False,
    }

    if role == "admin":
        return RedirectResponse("/admin/dashboard", status_code=302)
    if not request.session["user"].get("profile_completed"):
        return RedirectResponse("/candidate/complete-profile", status_code=302)
    return RedirectResponse("/candidate/dashboard", status_code=302)


@router.post("/logout")
@limiter.limit("30/minute")
async def logout(request: Request):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse("/?error=csrf", status_code=302)
    request.session.clear()
    return RedirectResponse("/", status_code=302)


@router.get("/dev/login")
@limiter.limit("30/minute")
async def dev_login(request: Request):
    """
    Dev-only login helper (bypasses Google OAuth).

    Enable with:
      ENVIRONMENT=development
      DEV_LOGIN_ENABLED=true
      DEV_LOGIN_TOKEN=<random>
    Then visit:
      /auth/dev/login?email=you@domain&role=candidate&token=...
    """
    if settings.environment.lower() == "production" or not settings.dev_login_enabled:
        return RedirectResponse("/?error=disabled", status_code=302)

    token = request.query_params.get("token") or request.headers.get("X-Dev-Token")
    if not token or not settings.dev_login_token or token != settings.dev_login_token:
        return RedirectResponse("/?error=unauthorized", status_code=302)

    email = normalize_email(request.query_params.get("email", ""))
    role = request.query_params.get("role", "candidate").strip().lower()
    if role not in {"candidate", "admin"}:
        role = "candidate"
    if not email:
        return RedirectResponse("/?error=email", status_code=302)

    user_doc = None
    try:
        user_doc = await UserService.upsert_google_user(
            google_sub=f"dev-{email}",
            login_email=email,
            name=request.query_params.get("name"),
            avatar_url=None,
            role=role,
        )
        # For dev convenience: mark profile completed.
        user_doc = await UserService.set_profile_completed(login_email=email, completed=True) or user_doc
    except RuntimeError:
        # DB not configured - still allow session for UI testing.
        pass

    request.session.clear()
    request.session["user"] = {
        "id": str(user_doc.get("_id")) if isinstance(user_doc, dict) and user_doc.get("_id") else None,
        "google_sub": f"dev-{email}",
        "login_email": email,
        "name": request.query_params.get("name"),
        "avatar_url": None,
        "role": role,
        "profile_completed": True if role == "admin" else True,
    }

    return RedirectResponse("/admin/dashboard" if role == "admin" else "/", status_code=302)
