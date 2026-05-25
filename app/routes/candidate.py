from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.csrf import validate_csrf
from pydantic import ValidationError

from app.schemas.user import CandidateProfileUpdate
from app.services.user_service import UserService
from app.services.application_service import ApplicationService
from app.services.job_service import JobService
from app.services.upload_service import UploadService
import httpx

from app.core.security import require_role
from app.core.templates import templates

router = APIRouter(prefix="/candidate", tags=["candidate"])

def _safe_session_value(v):
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _to_ddmmyyyy(raw: object) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    # Already DD-MM-YYYY
    if len(s) == 10 and s[2] == "-" and s[5] == "-":
        return s
    # ISO YYYY-MM-DD (or ISO datetime prefix)
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        yyyy, mm, dd = s[:10].split("-")
        if len(dd) == 2 and len(mm) == 2 and len(yyyy) == 4:
            return f"{dd}-{mm}-{yyyy}"
    return s


def _normalize_ddmmyyyy_input(raw: object) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    # Accept YYYY-MM-DD and convert
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        yyyy, mm, dd = s[:10].split("-")
        if len(dd) == 2 and len(mm) == 2 and len(yyyy) == 4:
            return f"{dd}-{mm}-{yyyy}"
    return s


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(require_role("candidate"))):
    return templates.TemplateResponse(
        request,
        "candidate/dashboard.html",
        {"user": user, "page_title": "Candidate Dashboard"},
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_get(request: Request, user=Depends(require_role("candidate"))):
    # Refresh user from DB for accurate prefill.
    view_user = dict(user)
    try:
        user_doc = await UserService.find_by_login_email(str(user.get("login_email") or ""))
        if user_doc:
            for k in (
                "name",
                "phone_number",
                "alternate_email",
                "current_city",
                "current_country",
                "linkedin_url",
                "date_of_birth",
                "gender",
                "nationality",
                "address",
                "postal_code",
                "university",
                "degree",
                "major",
                "graduation_year",
                "gpa",
                "experience_level",
                "years_of_experience",
                "skills",
                "experience_summary",
                "github_url",
                "portfolio_url",
                "other_links",
                "available_from",
                "hours_per_week",
                "resume_url",
                "resume_updated_at",
            ):
                if k in user_doc:
                    view_user[k] = _safe_session_value(user_doc.get(k))
            view_user["date_of_birth"] = _to_ddmmyyyy(user_doc.get("date_of_birth"))
            view_user["available_from"] = _to_ddmmyyyy(user_doc.get("available_from"))
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "candidate/profile.html",
        {"user": view_user, "page_title": "Your Profile"},
    )


@router.post("/profile")
async def profile_post(request: Request, user=Depends(require_role("candidate"))):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse("/candidate/profile?error=csrf", status_code=302)

    form = await request.form()
    resume_file = form.get("resume")

    other_links_raw = str(form.get("other_links") or "")
    other_links_raw = other_links_raw.replace("\r", "").replace("\n", ",")
    skills_raw = str(form.get("skills") or "")
    skills_raw = skills_raw.replace("\r", "").replace("\n", ",")

    try:
        payload = CandidateProfileUpdate(
            name=str(form.get("name") or ""),
            phone_number=str(form.get("phone_number") or ""),
            alternate_email=str(form.get("alternate_email") or ""),
            current_city=form.get("current_city"),
            current_country=form.get("current_country"),
            linkedin_url=form.get("linkedin_url"),
            date_of_birth=_normalize_ddmmyyyy_input(form.get("date_of_birth")),
            gender=form.get("gender"),
            nationality=form.get("nationality"),
            address=form.get("address"),
            postal_code=form.get("postal_code"),
            university=form.get("university"),
            degree=form.get("degree"),
            major=form.get("major"),
            graduation_year=form.get("graduation_year"),
            gpa=form.get("gpa"),
            experience_level=form.get("experience_level"),
            years_of_experience=form.get("years_of_experience"),
            skills=skills_raw,
            experience_summary=form.get("experience_summary"),
            github_url=form.get("github_url"),
            portfolio_url=form.get("portfolio_url"),
            other_links=other_links_raw,
        )
    except (ValidationError, ValueError):
        return RedirectResponse("/candidate/profile?error=validation", status_code=302)

    update_data = payload.model_dump()

    # Handle resume upload separately (file).
    if resume_file and getattr(resume_file, "filename", None):
        if not user.get("id"):
            return RedirectResponse("/candidate/profile?error=db", status_code=302)
        try:
            resume_url, resume_public_id = await UploadService.upload_profile_resume_pdf(
                file=resume_file, user_id=str(user.get("id"))
            )
            update_data["resume_url"] = resume_url
            update_data["resume_public_id"] = resume_public_id
            update_data["resume_updated_at"] = datetime.utcnow()
        except Exception:
            return RedirectResponse("/candidate/profile?error=resume", status_code=302)

    try:
        updated = await UserService.upsert_candidate_profile(
            login_email=str(user.get("login_email") or ""),
            data=update_data,
            profile_completed=True,
        )
    except RuntimeError:
        return RedirectResponse("/candidate/profile?error=db", status_code=302)

    request.session["user"]["profile_completed"] = bool(updated.get("profile_completed"))
    request.session["user"]["name"] = updated.get("name")
    return RedirectResponse("/candidate/profile?saved=1", status_code=302)


@router.get("/applications", response_class=HTMLResponse)
async def applications_list(request: Request, user=Depends(require_role("candidate"))):
    if not user.get("id"):
        return RedirectResponse("/", status_code=302)
    apps = await ApplicationService.list_applications_for_user(user_id=str(user.get("id")), limit=2000)
    # attach job titles
    job_ids = [str(a.get("job_id")) for a in apps if a.get("job_id")]
    jobs = {}
    try:
        job_docs = await JobService.get_jobs_by_ids(job_ids)
    except Exception:
        job_docs = []
    for j in job_docs:
        if j and j.get("_id"):
            jobs[str(j.get("_id"))] = j
    for a in apps:
        a["_job_title"] = jobs.get(str(a.get("job_id")), {}).get("title")
    return templates.TemplateResponse(
        request,
        "candidate/applications.html",
        {"user": user, "page_title": "My Applications", "applications": apps},
    )


@router.get("/applications/{application_id}", response_class=HTMLResponse)
async def application_detail(request: Request, application_id: str, user=Depends(require_role("candidate"))):
    if not user.get("id"):
        return RedirectResponse("/", status_code=302)
    app_doc = await ApplicationService.get_application_for_user(application_id=application_id, user_id=str(user.get("id")))
    if not app_doc:
        return RedirectResponse("/candidate/applications", status_code=302)
    job = None
    try:
        job = await JobService.get_job(str(app_doc.get("job_id")))
    except Exception:
        job = None
    return templates.TemplateResponse(
        request,
        "candidate/application_detail.html",
        {"user": user, "page_title": "Application", "application": app_doc, "job": job},
    )


@router.get("/applications/{application_id}/resume")
async def application_resume(request: Request, application_id: str, user=Depends(require_role("candidate"))):
    if not user.get("id"):
        return RedirectResponse("/", status_code=302)
    app_doc = await ApplicationService.get_application_for_user(
        application_id=application_id, user_id=str(user.get("id"))
    )
    if not app_doc:
        return RedirectResponse("/candidate/applications", status_code=302)
    resume_url = str(app_doc.get("resume_url") or "")
    resume_public_id = str(app_doc.get("resume_public_id") or "")
    if not resume_url and not resume_public_id:
        return RedirectResponse(f"/candidate/applications/{application_id}", status_code=302)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Try stored URL first (often works once PDF delivery is enabled in Cloudinary).
        r = await client.get(resume_url)
        if r.status_code in (401, 403, 404) and resume_public_id:
            signed = UploadService.signed_resume_url(public_id=resume_public_id, expires_in_seconds=300)
            r = await client.get(signed)
        r.raise_for_status()
        content = r.content

    headers = {
        "Content-Disposition": f'attachment; filename="resume_{application_id}.pdf"',
        "Content-Type": "application/pdf",
    }
    from fastapi.responses import StreamingResponse

    return StreamingResponse(iter([content]), headers=headers, media_type="application/pdf")


@router.get("/resume")
async def profile_resume(request: Request, user=Depends(require_role("candidate"))):
    if not user.get("id"):
        return RedirectResponse("/candidate/profile?error=db", status_code=302)

    user_doc = await UserService.find_by_login_email(str(user.get("login_email") or ""))
    resume_url = str((user_doc or {}).get("resume_url") or "")
    resume_public_id = str((user_doc or {}).get("resume_public_id") or "")
    if not resume_url and not resume_public_id:
        return RedirectResponse("/candidate/profile?error=resume_required", status_code=302)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(resume_url) if resume_url else None
        if (not r) or (r.status_code in (401, 403, 404) and resume_public_id):
            signed = UploadService.signed_resume_url(public_id=resume_public_id, expires_in_seconds=300)
            r = await client.get(signed)
        r.raise_for_status()
        content = r.content

    headers = {
        "Content-Disposition": 'attachment; filename="resume_profile.pdf"',
        "Content-Type": "application/pdf",
    }
    from fastapi.responses import StreamingResponse

    return StreamingResponse(iter([content]), headers=headers, media_type="application/pdf")


@router.get("/complete-profile", response_class=HTMLResponse)
async def complete_profile_get(request: Request, user=Depends(require_role("candidate"))):
    if user.get("profile_completed"):
        return RedirectResponse("/candidate/dashboard", status_code=302)
    view_user = dict(user)
    try:
        user_doc = await UserService.find_by_login_email(str(user.get("login_email") or ""))
        if user_doc:
            for k in (
                "name",
                "phone_number",
                "alternate_email",
                "current_city",
                "current_country",
                "linkedin_url",
                "date_of_birth",
                "gender",
                "nationality",
                "address",
                "postal_code",
                "university",
                "degree",
                "major",
                "graduation_year",
                "gpa",
                "experience_level",
                "years_of_experience",
                "skills",
                "experience_summary",
                "github_url",
                "portfolio_url",
                "other_links",
                "available_from",
                "hours_per_week",
                "resume_url",
                "resume_updated_at",
            ):
                if k in user_doc:
                    view_user[k] = _safe_session_value(user_doc.get(k))
            view_user["date_of_birth"] = _to_ddmmyyyy(user_doc.get("date_of_birth"))
            view_user["available_from"] = _to_ddmmyyyy(user_doc.get("available_from"))
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "candidate/complete_profile.html",
        {"user": view_user, "page_title": "Complete Profile"},
    )


@router.post("/complete-profile")
async def complete_profile_post(request: Request, user=Depends(require_role("candidate"))):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse("/candidate/complete-profile?error=csrf", status_code=302)

    form = await request.form()
    resume_file = form.get("resume")

    other_links_raw = str(form.get("other_links") or "")
    other_links_raw = other_links_raw.replace("\r", "").replace("\n", ",")
    skills_raw = str(form.get("skills") or "")
    skills_raw = skills_raw.replace("\r", "").replace("\n", ",")
    try:
        payload = CandidateProfileUpdate(
            name=str(form.get("name") or ""),
            phone_number=str(form.get("phone_number") or ""),
            alternate_email=str(form.get("alternate_email") or ""),
            current_city=form.get("current_city"),
            current_country=form.get("current_country"),
            linkedin_url=form.get("linkedin_url"),
            date_of_birth=_normalize_ddmmyyyy_input(form.get("date_of_birth")),
            gender=form.get("gender"),
            nationality=form.get("nationality"),
            address=form.get("address"),
            postal_code=form.get("postal_code"),
            university=form.get("university"),
            degree=form.get("degree"),
            major=form.get("major"),
            graduation_year=form.get("graduation_year"),
            gpa=form.get("gpa"),
            experience_level=form.get("experience_level"),
            years_of_experience=form.get("years_of_experience"),
            skills=skills_raw,
            experience_summary=form.get("experience_summary"),
            github_url=form.get("github_url"),
            portfolio_url=form.get("portfolio_url"),
            other_links=other_links_raw,
        )
    except (ValidationError, ValueError):
        return RedirectResponse("/candidate/complete-profile?error=validation", status_code=302)

    update_data = payload.model_dump()

    if resume_file and getattr(resume_file, "filename", None):
        if not user.get("id"):
            return RedirectResponse("/candidate/complete-profile?error=db", status_code=302)
        try:
            resume_url, resume_public_id = await UploadService.upload_profile_resume_pdf(
                file=resume_file, user_id=str(user.get("id"))
            )
            update_data["resume_url"] = resume_url
            update_data["resume_public_id"] = resume_public_id
            update_data["resume_updated_at"] = datetime.utcnow()
        except Exception:
            return RedirectResponse("/candidate/complete-profile?error=resume", status_code=302)
    try:
        updated = await UserService.upsert_candidate_profile(
            login_email=str(user.get("login_email") or ""),
            data=update_data,
            profile_completed=True,
        )
    except RuntimeError:
        return RedirectResponse("/candidate/complete-profile?error=db", status_code=302)

    request.session["user"]["profile_completed"] = bool(updated.get("profile_completed"))
    request.session["user"]["name"] = updated.get("name")
    next_url = str(request.session.pop("post_login_next", "") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return RedirectResponse(next_url, status_code=302)
    return RedirectResponse("/candidate/dashboard", status_code=302)
