from __future__ import annotations

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
    try:
        user_doc = await UserService.find_by_login_email(str(user.get("login_email") or ""))
        if user_doc:
            user["name"] = user_doc.get("name")
            user["phone_number"] = user_doc.get("phone_number")
            user["alternate_email"] = user_doc.get("alternate_email")
    except Exception:
        pass
    return templates.TemplateResponse(
        request,
        "candidate/profile.html",
        {"user": user, "page_title": "Your Profile"},
    )


@router.post("/profile")
async def profile_post(request: Request, user=Depends(require_role("candidate"))):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse("/candidate/profile?error=csrf", status_code=302)

    form = await request.form()
    try:
        payload = CandidateProfileUpdate(
            name=str(form.get("name") or ""),
            phone_number=str(form.get("phone_number") or ""),
            alternate_email=str(form.get("alternate_email") or ""),
        )
    except (ValidationError, ValueError):
        return RedirectResponse("/candidate/profile?error=validation", status_code=302)

    try:
        updated = await UserService.complete_candidate_profile(
            login_email=str(user.get("login_email") or ""),
            name=payload.name,
            phone_number=payload.phone_number,
            alternate_email=str(payload.alternate_email),
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
    job_ids = {a.get("job_id") for a in apps if a.get("job_id")}
    jobs = {}
    for jid in job_ids:
        try:
            j = await JobService.get_job(str(jid))
        except Exception:
            j = None
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


@router.get("/complete-profile", response_class=HTMLResponse)
async def complete_profile_get(request: Request, user=Depends(require_role("candidate"))):
    if user.get("profile_completed"):
        return RedirectResponse("/candidate/dashboard", status_code=302)
    return templates.TemplateResponse(
        request,
        "candidate/complete_profile.html",
        {"user": user, "page_title": "Complete Profile"},
    )


@router.post("/complete-profile")
async def complete_profile_post(request: Request, user=Depends(require_role("candidate"))):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse("/candidate/complete-profile?error=csrf", status_code=302)

    form = await request.form()
    try:
        payload = CandidateProfileUpdate(
            name=str(form.get("name") or ""),
            phone_number=str(form.get("phone_number") or ""),
            alternate_email=str(form.get("alternate_email") or ""),
        )
    except (ValidationError, ValueError):
        return RedirectResponse("/candidate/complete-profile?error=validation", status_code=302)
    try:
        updated = await UserService.complete_candidate_profile(
            login_email=str(user.get("login_email") or ""),
            name=payload.name,
            phone_number=payload.phone_number,
            alternate_email=str(payload.alternate_email),
        )
    except RuntimeError:
        return RedirectResponse("/candidate/complete-profile?error=db", status_code=302)

    request.session["user"]["profile_completed"] = bool(updated.get("profile_completed"))
    request.session["user"]["name"] = updated.get("name")
    return RedirectResponse("/candidate/dashboard", status_code=302)
