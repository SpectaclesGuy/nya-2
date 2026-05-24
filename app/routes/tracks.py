from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.core.csrf import validate_csrf
from app.core.security import require_role
from app.core.templates import templates
from app.services.application_service import ApplicationService
from app.services.job_service import JobService
from app.services.track_questionnaire_service import TrackQuestionnaireService
from app.services.user_service import UserService


router = APIRouter(prefix="/tracks", tags=["tracks"])


def _section_label(section: str) -> str:
    return "Project Internship" if section == "project_internship" else "Research Internship"


async def _latest_published_job_id_for_section(section: str) -> str | None:
    jobs = await JobService.list_published_jobs(limit=50, type=section)
    for j in jobs:
        if j.get("_id"):
            return str(j.get("_id"))
    return None


@router.get("/project-internship", response_class=HTMLResponse)
async def project_track_page(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse(
        request,
        "tracks/project.html",
        {"user": user, "page_title": "Project Internship Track"},
    )


@router.get("/research-internship", response_class=HTMLResponse)
async def research_track_page(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse(
        request,
        "tracks/research.html",
        {"user": user, "page_title": "Research Internship Track"},
    )


@router.get("/{section}/apply", response_class=HTMLResponse)
async def track_apply_get(request: Request, section: str, user=Depends(require_role("candidate"))):
    if section not in {"project-internship", "research-internship"}:
        return RedirectResponse("/", status_code=302)
    section_key = "project_internship" if section == "project-internship" else "research_internship"

    if not user.get("profile_completed"):
        return RedirectResponse("/candidate/complete-profile", status_code=302)

    user_doc = await UserService.find_by_login_email(str(user.get("login_email") or ""))
    if not (user_doc or {}).get("resume_url") and not (user_doc or {}).get("resume_public_id"):
        return RedirectResponse("/candidate/profile?error=resume_required", status_code=302)

    qdoc = await TrackQuestionnaireService.get_by_section(section=section_key)
    items = (qdoc.get("items") if qdoc else None) or (qdoc.get("questions") if qdoc else None) or []

    return templates.TemplateResponse(
        request,
        "tracks/apply.html",
        {
            "user": user,
            "page_title": f"Apply - {_section_label(section_key)}",
            "section_key": section_key,
            "section_label": _section_label(section_key),
            "items": items,
        },
    )


@router.post("/{section}/apply")
async def track_apply_post(request: Request, section: str, user=Depends(require_role("candidate"))):
    if section not in {"project-internship", "research-internship"}:
        return RedirectResponse("/", status_code=302)
    section_key = "project_internship" if section == "project-internship" else "research_internship"

    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse(f"/tracks/{section}/apply?error=csrf", status_code=302)

    if not user.get("profile_completed"):
        return RedirectResponse("/candidate/complete-profile", status_code=302)

    if not user.get("id"):
        return RedirectResponse(f"/tracks/{section}/apply?error=db", status_code=302)

    user_doc = await UserService.find_by_login_email(str(user.get("login_email") or ""))
    resume_url = str((user_doc or {}).get("resume_url") or "")
    resume_public_id = str((user_doc or {}).get("resume_public_id") or "")
    if not resume_url and not resume_public_id:
        return RedirectResponse("/candidate/profile?error=resume_required", status_code=302)

    qdoc = await TrackQuestionnaireService.get_by_section(section=section_key)
    items = (qdoc or {}).get("items") or (qdoc or {}).get("questions") or []
    # Normalize to item list with item_type
    normalized_items: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        t = str(it.get("item_type") or "question")
        if t not in {"section", "question"}:
            t = "question"
        out = dict(it)
        out["item_type"] = t
        normalized_items.append(out)
    questions = [i for i in normalized_items if str((i or {}).get("item_type") or "question") == "question"]

    form = await request.form()
    answers_out: list[dict] = []
    for q in sorted(questions, key=lambda x: int(x.get("order", 0))):
        qid = str(q.get("question_id") or "")
        qtype = str(q.get("question_type") or "text")
        required = bool(q.get("required"))
        options = [str(o) for o in (q.get("options") or [])]

        field = f"q_{qid}"
        if qtype == "multiple_choice":
            values = form.getlist(field)  # type: ignore[attr-defined]
            values = [str(v) for v in values if str(v)]
            if required and not values:
                return RedirectResponse(f"/tracks/{section}/apply?error=required", status_code=302)
            for v in values:
                if v not in options:
                    return RedirectResponse(f"/tracks/{section}/apply?error=invalid", status_code=302)
            answer_value: str | list[str] = values
        else:
            value = str(form.get(field) or "").strip()
            if required and not value:
                return RedirectResponse(f"/tracks/{section}/apply?error=required", status_code=302)
            if qtype == "single_choice" and value:
                if value not in options:
                    return RedirectResponse(f"/tracks/{section}/apply?error=invalid", status_code=302)
            answer_value = value

        answers_out.append(
            {
                "question_id": qid,
                "question_text": str(q.get("title") or ""),
                "question_type": qtype,
                "answer": answer_value,
            }
        )

    job_id_str = await _latest_published_job_id_for_section(section_key)
    if not job_id_str:
        return RedirectResponse(f"/tracks/{section}/apply?error=job", status_code=302)

    existing = await ApplicationService.find_by_job_and_user(job_id=job_id_str, user_id=str(user.get("id")))
    if existing and existing.get("_id"):
        return RedirectResponse(f"/candidate/applications/{existing.get('_id')}", status_code=302)

    candidate_phone = str((user_doc or {}).get("phone_number") or "")
    alternate_email = str((user_doc or {}).get("alternate_email") or "")

    app_id = await ApplicationService.create_application(
        data={
            "job_id": job_id_str,
            "user_id": str(user.get("id")),
            "candidate_name": str(user.get("name") or ""),
            "candidate_email": str(user.get("login_email") or ""),
            "candidate_phone": candidate_phone,
            "alternate_email": alternate_email,
            "resume_url": resume_url or None,
            "resume_public_id": resume_public_id or None,
            "track_section": section_key,
            "questionnaire_items": normalized_items,
            "answers": answers_out,
            "status": "submitted",
        }
    )
    return RedirectResponse(f"/candidate/applications/{app_id}", status_code=302)


@router.get("/admin-preview/{section}", response_class=HTMLResponse)
async def _track_questions_preview(request: Request, section: str, user=Depends(require_role("admin"))):
    if section not in {"project_internship", "research_internship"}:
        return RedirectResponse("/admin/dashboard", status_code=302)
    qdoc = await TrackQuestionnaireService.get_by_section(section=section)
    items = (qdoc or {}).get("items") or (qdoc or {}).get("questions") or []
    return templates.TemplateResponse(
        request,
        "tracks/apply.html",
        {
            "user": user,
            "page_title": f"Preview - {_section_label(section)}",
            "section_key": section,
            "section_label": _section_label(section),
            "items": items,
        },
    )
