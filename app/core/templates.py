from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.core.csrf import get_csrf_token

templates = Jinja2Templates(directory="app/templates")


def _csrf_token(request) -> str:
    return get_csrf_token(request.session)


templates.env.globals["csrf_token"] = _csrf_token
