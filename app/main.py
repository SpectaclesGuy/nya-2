from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.database import connect_to_mongo, disconnect_from_mongo
from app.core.middleware import (
    add_security_headers_middleware,
    add_session_middleware,
)
from app.core.rate_limit import limiter
from app.core.security import AuthRequired, auth_exception_handler
from app.routes import auth
from app.routes import candidate
from app.routes import admin
from app.routes import jobs
from app.routes import forges_api
from app.routes import forge_status_api
from app.routes import me_api
from app.routes import jobs_api


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(AuthRequired, auth_exception_handler)

    add_session_middleware(app)
    add_security_headers_middleware(app)

    app.include_router(auth.router)
    app.include_router(candidate.router)
    app.include_router(admin.router)
    app.include_router(jobs.router)
    app.include_router(forges_api.router)
    app.include_router(forge_status_api.router)
    app.include_router(me_api.router)
    app.include_router(jobs_api.router)

    # Static (future-proof; currently empty)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.on_event("startup")
    async def _startup() -> None:
        await connect_to_mongo()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await disconnect_from_mongo()

    @app.get("/", response_class=HTMLResponse)
    async def landing(request: Request) -> FileResponse:
        # Preserve the existing Stitch-generated landing page as-is.
        return FileResponse("index.html", media_type="text/html; charset=utf-8")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    return app


app = create_app()
