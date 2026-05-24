from __future__ import annotations

import csv
import io
from datetime import datetime
import json
import uuid

from fastapi import APIRouter, Depends, Request
import httpx

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse, StreamingResponse

from app.core.csrf import validate_csrf
from app.core.security import require_role
from app.core.templates import templates
from app.services.admin_service import AdminService
from app.services.application_service import ApplicationService
from app.services.job_service import JobService
from app.schemas.questions import JobQuestionUpsert

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(require_role("admin"))):
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {"user": user, "page_title": "Admin Dashboard"},
    )


@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user=Depends(require_role("admin"))):
    try:
        users = await AdminService.list_users(limit=1000)
    except RuntimeError:
        users = []
    for u in users:
        if u.get("_id"):
            u["_id"] = str(u["_id"])
    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {"user": user, "page_title": "Users", "users": users},
    )


@router.post("/users/{user_id}/role")
async def user_set_role(request: Request, user_id: str, user=Depends(require_role("admin"))):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse("/admin/users?error=csrf", status_code=302)

    form = await request.form()
    new_role = str(form.get("role") or "")
    # Prevent self-demotion.
    if user.get("id") and str(user.get("id")) == user_id and new_role != "admin":
        return RedirectResponse("/admin/users?error=self", status_code=302)

    try:
        await AdminService.set_role(
            target_user_id=user_id,
            new_role=new_role,
            performed_by_admin_id=str(user.get("id") or "") or None,
            performed_by_email=str(user.get("login_email") or ""),
        )
    except Exception as e:
        return RedirectResponse(f"/admin/users?error={type(e).__name__}", status_code=302)
    return RedirectResponse("/admin/users", status_code=302)


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_admin(request: Request, user=Depends(require_role("admin"))):
    try:
        jobs = await JobService.list_jobs_admin(limit=1000)
    except RuntimeError:
        jobs = []
    for j in jobs:
        if j.get("_id"):
            j["_id"] = str(j["_id"])
    return templates.TemplateResponse(
        request,
        "admin/jobs_list.html",
        {"user": user, "page_title": "Jobs (Admin)", "jobs": jobs},
    )


@router.get("/jobs/create", response_class=HTMLResponse)
async def jobs_create_get(request: Request, user=Depends(require_role("admin"))):
    return templates.TemplateResponse(
        request,
        "admin/job_form.html",
        {"user": user, "page_title": "Create Job", "job": None, "action": "/admin/jobs/create"},
    )


@router.post("/jobs/create")
async def jobs_create_post(request: Request, user=Depends(require_role("admin"))):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse("/admin/jobs/create?error=csrf", status_code=302)

    form = await request.form()
    data = {
        "type": str(form.get("type") or "").strip() or "project_internship",
        "title": str(form.get("title") or "").strip(),
        "company_or_team": str(form.get("company_or_team") or "").strip(),
        "location": str(form.get("location") or "").strip(),
        "job_type": str(form.get("job_type") or "").strip(),
        "description": str(form.get("description") or "").strip(),
    }
    if data["type"] not in {"project_internship", "research_internship"}:
        return RedirectResponse("/admin/jobs/create?error=type", status_code=302)
    deadline_raw = str(form.get("deadline") or "").strip()
    if deadline_raw:
        try:
            data["deadline"] = datetime.fromisoformat(deadline_raw)
        except ValueError:
            return RedirectResponse("/admin/jobs/create?error=deadline", status_code=302)

    try:
        job_id = await JobService.create_job(data=data, created_by=str(user.get("id") or "") or None)
    except Exception:
        return RedirectResponse("/admin/jobs/create?error=db", status_code=302)

    return RedirectResponse(f"/admin/jobs/{job_id}/edit", status_code=302)


@router.get("/jobs/{job_id}/edit", response_class=HTMLResponse)
async def jobs_edit_get(request: Request, job_id: str, user=Depends(require_role("admin"))):
    try:
        job = await JobService.get_job(job_id)
    except Exception:
        job = None
    if not job:
        return RedirectResponse("/admin/jobs?error=notfound", status_code=302)
    job["_id"] = str(job["_id"])
    return templates.TemplateResponse(
        request,
        "admin/job_form.html",
        {"user": user, "page_title": "Edit Job", "job": job, "action": f"/admin/jobs/{job_id}/edit"},
    )


@router.post("/jobs/{job_id}/edit")
async def jobs_edit_post(request: Request, job_id: str, user=Depends(require_role("admin"))):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse(f"/admin/jobs/{job_id}/edit?error=csrf", status_code=302)

    form = await request.form()
    data = {
        "type": str(form.get("type") or "").strip() or "project_internship",
        "title": str(form.get("title") or "").strip(),
        "company_or_team": str(form.get("company_or_team") or "").strip(),
        "location": str(form.get("location") or "").strip(),
        "job_type": str(form.get("job_type") or "").strip(),
        "description": str(form.get("description") or "").strip(),
    }
    if data["type"] not in {"project_internship", "research_internship"}:
        return RedirectResponse(f"/admin/jobs/{job_id}/edit?error=type", status_code=302)
    deadline_raw = str(form.get("deadline") or "").strip()
    data["deadline"] = None
    if deadline_raw:
        try:
            data["deadline"] = datetime.fromisoformat(deadline_raw)
        except ValueError:
            return RedirectResponse(f"/admin/jobs/{job_id}/edit?error=deadline", status_code=302)

    try:
        await JobService.update_job(job_id=job_id, data=data)
    except Exception:
        return RedirectResponse(f"/admin/jobs/{job_id}/edit?error=db", status_code=302)
    return RedirectResponse("/admin/jobs", status_code=302)


@router.post("/jobs/{job_id}/delete")
async def jobs_delete(request: Request, job_id: str, user=Depends(require_role("admin"))):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse("/admin/jobs?error=csrf", status_code=302)
    await JobService.delete_job(job_id)
    return RedirectResponse("/admin/jobs", status_code=302)


@router.post("/jobs/{job_id}/status")
async def jobs_set_status(request: Request, job_id: str, user=Depends(require_role("admin"))):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse("/admin/jobs?error=csrf", status_code=302)
    form = await request.form()
    status = str(form.get("status") or "")
    try:
        await JobService.set_status(job_id=job_id, status=status)
    except Exception:
        return RedirectResponse("/admin/jobs?error=status", status_code=302)
    return RedirectResponse("/admin/jobs", status_code=302)


@router.get("/jobs/{job_id}/questions", response_class=HTMLResponse)
async def job_questions_get(request: Request, job_id: str, user=Depends(require_role("admin"))):
    try:
        job = await JobService.get_job(job_id)
    except Exception:
        job = None
    if not job:
        return RedirectResponse("/admin/jobs?error=notfound", status_code=302)
    job["_id"] = str(job["_id"])
    questions = job.get("questions") or []
    return templates.TemplateResponse(
        request,
        "admin/job_questions.html",
        {"user": user, "page_title": "Job Questions", "job": job, "questions_json": json.dumps(questions, default=str)},
    )


@router.post("/jobs/{job_id}/questions")
async def job_questions_post(request: Request, job_id: str, user=Depends(require_role("admin"))):
    try:
        await validate_csrf(request)
    except Exception:
        return RedirectResponse(f"/admin/jobs/{job_id}/questions?error=csrf", status_code=302)

    form = await request.form()
    raw = str(form.get("questions_json") or "[]")
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Invalid payload")
    except Exception:
        return RedirectResponse(f"/admin/jobs/{job_id}/questions?error=payload", status_code=302)

    normalized: list[dict] = []
    try:
        for idx, q in enumerate(data):
            if not isinstance(q, dict):
                continue
            qid = str(q.get("question_id") or uuid.uuid4().hex)
            title = str(q.get("title") or "").strip()
            help_text = str(q.get("help_text") or "").strip() or None
            qtype = str(q.get("question_type") or "text")
            required = bool(q.get("required"))
            options = q.get("options") or []
            if not isinstance(options, list):
                options = []
            options = [str(o).strip() for o in options if str(o).strip()]
            order = int(q.get("order") if q.get("order") is not None else idx)
            validated = JobQuestionUpsert(
                question_id=qid,
                title=title,
                help_text=help_text,
                question_type=qtype,  # type: ignore[arg-type]
                required=required,
                options=options,
                order=order,
            )
            normalized.append(validated.model_dump())
    except Exception:
        return RedirectResponse(f"/admin/jobs/{job_id}/questions?error=validation", status_code=302)

    # Sort by order and compact orders.
    normalized.sort(key=lambda x: int(x.get("order", 0)))
    for i, q in enumerate(normalized):
        q["order"] = i

    try:
        await JobService.set_questions(job_id=job_id, questions=normalized)
    except Exception:
        return RedirectResponse(f"/admin/jobs/{job_id}/questions?error=db", status_code=302)

    return RedirectResponse(f"/admin/jobs/{job_id}/questions?saved=1", status_code=302)


@router.get("/submissions", response_class=HTMLResponse)
async def submissions(request: Request, user=Depends(require_role("admin"))):
    job_id = request.query_params.get("job_id")
    try:
        apps = await ApplicationService.list_applications(job_id=job_id, limit=5000)
        jobs = await JobService.list_jobs_admin(limit=2000)
    except RuntimeError:
        apps, jobs = [], []

    job_map = {str(j.get("_id")): j for j in jobs if j.get("_id")}
    for a in apps:
        if a.get("_id"):
            a["_id"] = str(a["_id"])
        a["_job_title"] = job_map.get(str(a.get("job_id")), {}).get("title")

    job_options = [{"id": str(j.get("_id")), "title": j.get("title")} for j in jobs if j.get("_id")]
    return templates.TemplateResponse(
        request,
        "admin/submissions.html",
        {
            "user": user,
            "page_title": "Submissions",
            "applications": apps,
            "job_options": job_options,
            "selected_job_id": job_id or "",
        },
    )


@router.get("/jobs/{job_id}/stats", response_class=HTMLResponse)
async def job_stats(request: Request, job_id: str, user=Depends(require_role("admin"))):
    job = await JobService.get_job(job_id)
    if not job:
        return RedirectResponse("/admin/jobs?error=notfound", status_code=302)
    job["_id"] = str(job["_id"])
    apps = await ApplicationService.list_applications(job_id=job["_id"], limit=50000)

    status_counts: dict[str, int] = {}
    for a in apps:
        status_counts[a.get("status", "submitted")] = status_counts.get(a.get("status", "submitted"), 0) + 1

    # Question-wise stats
    q_stats: list[dict] = []
    questions = sorted((job.get("questions") or []), key=lambda x: int(x.get("order", 0)))
    for q in questions:
        qid = str(q.get("question_id"))
        qtype = str(q.get("question_type"))
        title = str(q.get("title") or "")
        options = [str(o) for o in (q.get("options") or [])]

        if qtype in {"single_choice", "multiple_choice"}:
            counts = {opt: 0 for opt in options}
            total = 0
            for a in apps:
                for ans in (a.get("answers") or []):
                    if str(ans.get("question_id")) != qid:
                        continue
                    val = ans.get("answer")
                    if qtype == "multiple_choice" and isinstance(val, list):
                        for v in val:
                            if v in counts:
                                counts[v] += 1
                                total += 1
                    elif isinstance(val, str):
                        if val in counts:
                            counts[val] += 1
                            total += 1
            dist = [
                {"option": opt, "count": counts.get(opt, 0), "pct": (counts.get(opt, 0) / total * 100.0) if total else 0.0}
                for opt in options
            ]
            q_stats.append({"title": title, "type": qtype, "distribution": dist, "total": total})
        else:
            # Text: show count and recent samples (no PII beyond what is already in submission).
            texts: list[str] = []
            for a in apps:
                for ans in (a.get("answers") or []):
                    if str(ans.get("question_id")) != qid:
                        continue
                    val = ans.get("answer")
                    if isinstance(val, str) and val.strip():
                        texts.append(val.strip())
            q_stats.append({"title": title, "type": qtype, "count": len(texts), "samples": texts[:25]})

    return templates.TemplateResponse(
        request,
        "admin/job_stats.html",
        {
            "user": user,
            "page_title": "Job Stats",
            "job": job,
            "total_apps": len(apps),
            "status_counts": status_counts,
            "q_stats": q_stats,
        },
    )


@router.get("/jobs/{job_id}/responses", response_class=HTMLResponse)
async def job_responses(request: Request, job_id: str, user=Depends(require_role("admin"))):
    job = await JobService.get_job(job_id)
    if not job:
        return RedirectResponse("/admin/jobs?error=notfound", status_code=302)
    job["_id"] = str(job["_id"])
    apps = await ApplicationService.list_applications_for_job(job_id=job["_id"], limit=50000)
    return templates.TemplateResponse(
        request,
        "admin/job_responses.html",
        {
            "user": user,
            "page_title": "Job Responses",
            "job": job,
            "applications": apps,
        },
    )


@router.get("/applications/{application_id}", response_class=HTMLResponse)
async def application_detail_admin(request: Request, application_id: str, user=Depends(require_role("admin"))):
    app_doc = await ApplicationService.get_application_admin(application_id=application_id)
    if not app_doc:
        return RedirectResponse("/admin/submissions?error=notfound", status_code=302)
    job = None
    try:
        job = await JobService.get_job(str(app_doc.get("job_id")))
    except Exception:
        job = None
    return templates.TemplateResponse(
        request,
        "admin/application_detail.html",
        {"user": user, "page_title": "Application", "application": app_doc, "job": job},
    )


@router.get("/applications/{application_id}/resume")
async def application_resume_admin(request: Request, application_id: str, user=Depends(require_role("admin"))):
    app_doc = await ApplicationService.get_application_admin(application_id=application_id)
    if not app_doc or not app_doc.get("resume_url"):
        return RedirectResponse("/admin/submissions?error=resume", status_code=302)

    resume_url = str(app_doc.get("resume_url"))
    resume_public_id = str(app_doc.get("resume_public_id") or "")

    # Proxy download through our backend to avoid browser/Cloudinary oddities.
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Try stored URL first (often works once PDF delivery is enabled in Cloudinary).
        r = await client.get(resume_url)
        if r.status_code in (401, 403, 404) and resume_public_id:
            from app.services.upload_service import UploadService

            signed = UploadService.signed_resume_url(public_id=resume_public_id, expires_in_seconds=300)
            r = await client.get(signed)
        r.raise_for_status()
        content = r.content

    headers = {
        "Content-Disposition": f'attachment; filename="resume_{application_id}.pdf"',
        "Content-Type": "application/pdf",
    }
    return StreamingResponse(iter([content]), headers=headers, media_type="application/pdf")


@router.get("/submissions/download")
async def submissions_download(request: Request, user=Depends(require_role("admin"))):
    job_id = request.query_params.get("job_id")
    apps = await ApplicationService.list_applications(job_id=job_id, limit=50000)

    # Attach job titles (precomputed; can't await inside generator).
    jobs: dict[str, str] = {}
    try:
        for j in await JobService.list_jobs_admin(limit=5000):
            if j.get("_id"):
                jobs[str(j["_id"])] = str(j.get("title") or "")
    except Exception:
        jobs = {}

    def iter_csv():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "application_id",
                "job_id",
                "job_title",
                "candidate_name",
                "candidate_email",
                "candidate_phone",
                "alternate_email",
                "resume_url",
                "status",
                "created_at",
                "answers_json",
            ]
        )
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        for a in apps:
            answers_json = ""
            try:
                answers_json = json.dumps(a.get("answers") or [], ensure_ascii=False)
            except Exception:
                answers_json = ""
            writer.writerow(
                [
                    str(a.get("_id", "")),
                    str(a.get("job_id", "")),
                    jobs.get(str(a.get("job_id", "")), ""),
                    a.get("candidate_name", ""),
                    a.get("candidate_email", ""),
                    a.get("candidate_phone", ""),
                    a.get("alternate_email", ""),
                    a.get("resume_url", ""),
                    a.get("status", ""),
                    a.get("created_at", ""),
                    answers_json,
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    filename = "submissions.csv" if not job_id else f"submissions_{job_id}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter_csv(), media_type="text/csv; charset=utf-8", headers=headers)
