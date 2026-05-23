from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from app.core.csrf import validate_csrf
from app.core.security import get_session_user
from app.core.security import require_role
from app.core.templates import templates
from app.services.application_service import ApplicationService
from app.services.job_service import JobService
from app.services.upload_service import UploadService
from app.services.user_service import UserService

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_list(request: Request):
    user = get_session_user(request)
    try:
        jobs = await JobService.list_published_jobs(limit=200)
    except RuntimeError:
        jobs = []
    for j in jobs:
        if j.get("_id"):
            j["_id"] = str(j["_id"])
    return templates.TemplateResponse(
        request,
        "jobs/list.html",
        {"user": user, "page_title": "Jobs", "jobs": jobs},
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str):
    user = get_session_user(request)
    try:
        job = await JobService.get_published_job(job_id)
    except Exception:
        job = None
    if job and job.get("_id"):
        job["_id"] = str(job["_id"])
    existing_app_id = None
    if user and user.get("role") == "candidate" and user.get("id") and job:
        try:
            existing = await ApplicationService.find_by_job_and_user(
                job_id=str(job.get("_id")), user_id=str(user.get("id"))
            )
            if existing and existing.get("_id"):
                existing_app_id = str(existing.get("_id"))
        except Exception:
            existing_app_id = None

    return templates.TemplateResponse(
        request,
        "jobs/detail.html",
        {
            "user": user,
            "page_title": "Job Details",
            "job_id": job_id,
            "job": job,
            "existing_app_id": existing_app_id,
        },
    )


@router.get("/jobs/{job_id}/apply", response_class=HTMLResponse)
async def job_apply_get(request: Request, job_id: str, user=Depends(require_role("candidate"))):
    if not user.get("profile_completed"):
        return RedirectResponse("/candidate/complete-profile", status_code=302)

    job = await JobService.get_published_job(job_id)
    if not job:
        return RedirectResponse(f"/jobs/{job_id}", status_code=302)
    job["_id"] = str(job["_id"])

    return templates.TemplateResponse(
        request,
        "jobs/apply.html",
        {"user": user, "page_title": "Apply", "job": job},
    )


@router.post("/jobs/{job_id}/apply")
async def job_apply_post(
    request: Request,
    job_id: str,
    resume: UploadFile = File(...),
    user=Depends(require_role("candidate")),
):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse(f"/jobs/{job_id}/apply?error=csrf", status_code=302)

    if not user.get("profile_completed"):
        return RedirectResponse("/candidate/complete-profile", status_code=302)

    if not user.get("id"):
        return RedirectResponse(f"/jobs/{job_id}?error=db", status_code=302)

    job = await JobService.get_published_job(job_id)
    if not job:
        return RedirectResponse(f"/jobs/{job_id}?error=notfound", status_code=302)

    job_id_str = str(job.get("_id"))
    user_id = str(user.get("id"))

    # Prevent duplicate submissions.
    existing = await ApplicationService.find_by_job_and_user(job_id=job_id_str, user_id=user_id)
    if existing and existing.get("_id"):
        return RedirectResponse(f"/candidate/applications/{existing.get('_id')}", status_code=302)

    form = await request.form()
    questions = (job.get("questions") or [])

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
                return RedirectResponse(f"/jobs/{job_id}/apply?error=required", status_code=302)
            for v in values:
                if v not in options:
                    return RedirectResponse(f"/jobs/{job_id}/apply?error=invalid", status_code=302)
            answer_value: str | list[str] = values
        else:
            value = str(form.get(field) or "").strip()
            if required and not value:
                return RedirectResponse(f"/jobs/{job_id}/apply?error=required", status_code=302)
            if qtype == "single_choice" and value:
                if value not in options:
                    return RedirectResponse(f"/jobs/{job_id}/apply?error=invalid", status_code=302)
            answer_value = value

        answers_out.append(
            {
                "question_id": qid,
                "question_text": str(q.get("title") or ""),
                "question_type": qtype,
                "answer": answer_value,
            }
        )

    try:
        resume_url, resume_public_id = await UploadService.upload_resume_pdf(
            file=resume, user_id=user_id, job_id=job_id_str
        )
    except Exception:
        return RedirectResponse(f"/jobs/{job_id}/apply?error=resume", status_code=302)

    # Pull candidate fields from DB (authoritative).
    user_doc = await UserService.find_by_login_email(str(user.get("login_email") or ""))
    candidate_phone = str((user_doc or {}).get("phone_number") or "")
    alternate_email = str((user_doc or {}).get("alternate_email") or "")

    app_id = await ApplicationService.create_application(
        data={
            "job_id": job_id_str,
            "user_id": user_id,
            "candidate_name": str(user.get("name") or ""),
            "candidate_email": str(user.get("login_email") or ""),
            "candidate_phone": candidate_phone,
            "alternate_email": alternate_email,
            "resume_url": resume_url,
            "resume_public_id": resume_public_id,
            "answers": answers_out,
            "status": "submitted",
        }
    )

    return RedirectResponse(f"/candidate/applications/{app_id}", status_code=302)
