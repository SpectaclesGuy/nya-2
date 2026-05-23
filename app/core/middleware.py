from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings


def add_session_middleware(app: FastAPI) -> None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        https_only=settings.cookie_secure_effective,
        same_site=settings.cookie_samesite,
        session_cookie="nya_session",
        max_age=60 * 60 * 24 * 7,
    )

    # CORS is primarily relevant if/when we add JS-driven flows; keep it tight.
    origins = settings.allowed_origins_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-CSRF-Token"],
        )


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                existing = list(message.get("headers") or [])
                # Don't coerce to dict: would drop duplicate headers (e.g., multiple Set-Cookie).
                add = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
                    # Tailwind CDN + Google fonts currently required by Stitch landing page.
                    (
                        b"content-security-policy",
                        b"default-src 'self'; "
                        b"img-src 'self' data:; "
                        b"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                        b"font-src 'self' https://fonts.gstatic.com; "
                        b"script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
                        b"connect-src 'self'; "
                        b"frame-ancestors 'none';",
                    ),
                ]
                message["headers"] = existing + add
            await send(message)

        await self.app(scope, receive, send_wrapper)


def add_security_headers_middleware(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)
