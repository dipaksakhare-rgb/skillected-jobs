"""Admin dashboard (§40–42, §67–68) — SSR pages + action endpoints, RBAC + CSRF + audit."""
from __future__ import annotations

import json

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core import database as db
from app.core.config import get_settings
from app.core.security import (client_ip, create_session, destroy_session, hash_password,
                               limiter, require_role, verify_csrf, verify_password)
from app.repositories import companies_repo, courses_repo, jobs_repo, sources_repo, stats_repo, users_repo
from app.services import scoring

settings = get_settings()
router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(settings.templates_dir))

ADMIN_ROLES = ("admin", "placement_officer")


def _ctx(request: Request, **extra) -> dict:
    sess = request.scope.get("session_data")
    return {"request": request, "session": sess, "pending_review": jobs_repo.pending_review_count(),
            **extra}


def _audit(user_id: int | None, action: str, entity_type: str, entity_id: int | None,
           details: str = "", ip: str = "") -> None:
    users_repo.log_admin_action(user_id, action, entity_type, entity_id, details, ip)


# ---------------------------------------------------------------- auth

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.scope.get("session_data"):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "admin/login.html", _ctx(request))


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    ip = client_ip(request)
    if not limiter.check("admin-login", ip, 10, 300):
        raise HTTPException(status_code=429, detail="Too many attempts; try later")
    user = users_repo.get_user_by_email(email.strip())
    if not user or not verify_password(password, user["password_hash"]):
        _audit(user["user_id"] if user else None, "login_failed", "user", None, email, ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token, _csrf = create_session(user["user_id"])
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(settings.session_cookie, token, httponly=True, samesite="lax",
                    secure=settings.is_prod)
    _audit(user["user_id"], "login", "user", user["user_id"], "", ip)
    return resp


@router.get("/logout")
def logout(request: Request):
    sess = request.scope.get("session_data")
    if sess:
        destroy_session(request)
    resp = RedirectResponse("/admin/login", status_code=303)
    resp.delete_cookie(settings.session_cookie)
    return resp


# ---------------------------------------------------------------- overview (§41)

@router.get("", response_class=HTMLResponse)
def overview(request: Request):
    require_role(*ADMIN_ROLES)(request)
    stats = stats_repo.platform_stats()
    metrics = _admin_metrics(stats)
    sources = sources_repo.list_sources()
    health = [{"company": s["company_name"], "status_label": sources_repo.compute_health(s)[0],
               "css": sources_repo.compute_health(s)[1], "last_checked": s["last_checked_at"]}
              for s in sources[:6]]
    events = stats_repo.latest_events(8)
    radar_rows = stats_repo.placement_radar()["by_domain"]
    return templates.TemplateResponse(request, "admin/overview.html", _ctx(
        request, stats=stats, metrics=metrics, source_health=health, events=events,
        radar_rows=radar_rows))


def _admin_metrics(stats: dict) -> dict:
    row = db.query_one(
        """SELECT
             SUM(CASE WHEN verification_status='pending' THEN 1 ELSE 0 END) AS pending,
             SUM(CASE WHEN verification_status='needs_review' THEN 1 ELSE 0 END) AS needs_review,
             SUM(CASE WHEN job_status='expired' THEN 1 ELSE 0 END) AS expired,
             SUM(CASE WHEN job_status='active' AND verification_status='approved' THEN 1 ELSE 0 END) AS verified
           FROM jobs WHERE is_demo=0""")
    row = dict(row) if row else {}
    row_q = db.query_one("SELECT COUNT(*) AS c FROM companies")
    clicks = db.query_one("SELECT COUNT(*) AS c FROM application_clicks")
    return {
        "total_jobs": stats["total_active_jobs"],
        "companies": int(row_q["c"]) if row_q else 0,
        "apply_clicks": int(clicks["c"]) if clicks else 0,
        "pending": int(row.get("pending") or 0),
        "needs_review": int(row.get("needs_review") or 0),
        "expired": int(row.get("expired") or 0),
        "verified": int(row.get("verified") or 0),
    }


# ---------------------------------------------------------------- jobs review (§67)

@router.get("/jobs", response_class=HTMLResponse)
def admin_jobs(request: Request, status: str = "", verification: str = "", q: str = "",
               page: int = 1):
    require_role(*ADMIN_ROLES)(request)
    jobs, total = jobs_repo.admin_list(status=status, verification=verification, q=q,
                                       page=page, per_page=25)
    pages = max(1, (total + 24) // 25)
    return templates.TemplateResponse(request, "admin/jobs.html", _ctx(
        request, jobs=jobs, total=total, page=page, pages=pages,
        f_status=status, f_verification=verification, f_q=q,
        statuses=("active", "expired", "closed", "draft"),
        verifications=("pending", "approved", "needs_review", "rejected")))


def _csrf_guard(request: Request, token: str) -> dict:
    sess = require_role(*ADMIN_ROLES)(request)
    verify_csrf(request, token)
    return sess


def _set_job(job_id: int, updates: dict, sess: dict, action: str) -> None:
    sets = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [job_id]
    db.execute(f"UPDATE jobs SET {sets}, updated_at = datetime('now') WHERE job_id = ?", params)
    _audit(sess["user_id"], action, "job", job_id, json.dumps(updates), client_ip_by_request(sess))


def client_ip_by_request(sess: dict) -> str:  # pragma: no cover - simple helper
    return sess.get("ip", "")


@router.post("/jobs/{job_id}/approve")
def approve_job(request: Request, job_id: int, csrf: str = Form("", alias="_csrf")):
    sess = _csrf_guard(request, csrf)
    _set_job(job_id, {"verification_status": "approved",
                      "published_at": scoring.now_utc_iso()}, sess, "approve_job")
    return RedirectResponse(request.headers.get("referer") or "/admin/jobs", status_code=303)


@router.post("/jobs/{job_id}/reject")
def reject_job(request: Request, job_id: int, csrf: str = Form("", alias="_csrf")):
    sess = _csrf_guard(request, csrf)
    _set_job(job_id, {"verification_status": "rejected", "job_status": "draft"}, sess, "reject_job")
    return RedirectResponse(request.headers.get("referer") or "/admin/jobs", status_code=303)


@router.post("/jobs/{job_id}/expire")
def expire_job(request: Request, job_id: int, csrf: str = Form("", alias="_csrf")):
    sess = _csrf_guard(request, csrf)
    _set_job(job_id, {"job_status": "expired"}, sess, "expire_job")
    return RedirectResponse(request.headers.get("referer") or "/admin/jobs", status_code=303)


@router.post("/jobs/{job_id}/application-url")
def set_application_url(request: Request, job_id: int, application_url: str = Form(...),
                        csrf: str = Form("", alias="_csrf")):
    sess = _csrf_guard(request, csrf)
    if not application_url.startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="Invalid URL")
    _set_job(job_id, {"application_url": application_url}, sess, "replace_application_url")
    return RedirectResponse("/admin/jobs", status_code=303)


@router.post("/jobs/bulk")
def bulk_actions(request: Request, action: str = Form(...), selected: list[int] = Form([]),
                 csrf: str = Form("", alias="_csrf")):
    sess = _csrf_guard(request, csrf)
    updates = {"approve": {"verification_status": "approved"},
               "reject": {"verification_status": "rejected", "job_status": "draft"},
               "expire": {"job_status": "expired"}}.get(action)
    if not updates:
        raise HTTPException(status_code=400, detail="Unknown bulk action")
    for job_id in selected:
        _set_job(job_id, updates, sess, f"bulk_{action}")
    return RedirectResponse("/admin/jobs", status_code=303)


# ---------------------------------------------------------------- companies (§40)

@router.get("/companies", response_class=HTMLResponse)
def admin_companies(request: Request):
    require_role(*ADMIN_ROLES)(request)
    companies = companies_repo.list_companies(limit=200)
    return templates.TemplateResponse(request, "admin/companies.html", _ctx(
        request, companies=companies))


@router.get("/sources", response_class=HTMLResponse)
def admin_sources(request: Request):
    require_role(*ADMIN_ROLES)(request)
    sources = []
    for s in sources_repo.list_sources():
        label, css = sources_repo.compute_health(s)
        s = dict(s)
        s["health_label"], s["health_css"] = label, css
        sources.append(s)
    companies = companies_repo.list_companies(limit=500)
    return templates.TemplateResponse(request, "admin/sources.html", _ctx(
        request, sources=sources, companies=companies))


@router.post("/sources")
def add_source(request: Request, company_id: int = Form(...), source_url: str = Form(...),
               source_type: str = Form(...), ats_type: str = Form(""),
               crawl_frequency_minutes: int = Form(720), csrf: str = Form("", alias="_csrf")):
    _csrf_guard(request, csrf)
    if source_type not in ("official_careers", "official_ats", "permitted_public"):
        raise HTTPException(status_code=400, detail="Invalid source type")
    if crawl_frequency_minutes not in (15, 30, 60, 360, 720, 1440):
        raise HTTPException(status_code=400, detail="Invalid frequency")
    sources_repo.create_source(company_id, source_url, source_type, ats_type,
                               crawl_frequency_minutes)
    return RedirectResponse("/admin/sources", status_code=303)


@router.post("/sources/{source_id}/toggle")
def toggle_source(request: Request, source_id: int, csrf: str = Form("", alias="_csrf")):
    _csrf_guard(request, csrf)
    src = sources_repo.get_source(source_id)
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")
    sources_repo.update_source(source_id, active=0 if src["active"] else 1,
                               status="disabled" if src["active"] else "never_checked")
    return RedirectResponse("/admin/sources", status_code=303)


@router.post("/sources/{source_id}/frequency")
def set_frequency(request: Request, source_id: int, crawl_frequency_minutes: int = Form(...),
                  csrf: str = Form("", alias="_csrf")):
    _csrf_guard(request, csrf)
    if crawl_frequency_minutes not in (15, 30, 60, 360, 720, 1440):
        raise HTTPException(status_code=400, detail="Invalid frequency")
    sources_repo.update_source(source_id, crawl_frequency_minutes=crawl_frequency_minutes)
    return RedirectResponse("/admin/sources", status_code=303)


# ---------------------------------------------------------------- crawl automation (§52–53)

@router.get("/crawler", response_class=HTMLResponse)
def crawler_page(request: Request):
    require_role(*ADMIN_ROLES)(request)
    from app.crawler import scheduler
    history = scheduler.report_history(10)
    return templates.TemplateResponse(request, "admin/crawler.html", _ctx(
        request, history=history, last=scheduler.last_report()))


@router.post("/crawler/run")
def crawler_run(request: Request, csrf: str = Form("", alias="_csrf")):
    sess = _csrf_guard(request, csrf)
    from app.crawler.ingest import run_crawl
    report = run_crawl(trigger="manual")
    _audit(sess["user_id"], "crawl_run", "crawl", report.get("run_id"),
           json.dumps({k: v for k, v in report.items() if k != "run_id"}), "")
    return RedirectResponse("/admin/crawler", status_code=303)


@router.post("/expiry/run")
def expiry_run(request: Request, csrf: str = Form("", alias="_csrf")):
    sess = _csrf_guard(request, csrf)
    from app.crawler.ingest import run_expiry_check
    result = run_expiry_check()
    _audit(sess["user_id"], "expiry_run", "jobs", None,
           f"checked={result['checked']} expired={result['expired']}", "")
    return RedirectResponse("/admin/crawler", status_code=303)


@router.post("/jobs/{job_id}/regenerate")
def regenerate_assets(request: Request, job_id: int, asset: str = Form(...),
                      csrf: str = Form("", alias="_csrf")):
    """§67 — regenerate poster / QR / WhatsApp content for one job."""
    sess = _csrf_guard(request, csrf)
    job = jobs_repo.get_job(job_id, published_only=False)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if asset == "poster":
        from app.services import poster as poster_svc
        from app.services.content import qr_png
        png = poster_svc.poster_png(job, f"{settings.app_base_url}/apply/{job_id}",
                                    qr_png(f"{settings.app_base_url}/apply/{job_id}"))
        path = poster_svc.save_poster(job_id, png)
        _audit(sess["user_id"], "regenerate_poster", "job", job_id, str(path), "")
    else:
        raise HTTPException(status_code=400, detail="Unknown asset")
    return RedirectResponse("/admin/jobs", status_code=303)


# ---------------------------------------------------------------- settings (§68)

@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    require_role("admin")(request)
    return templates.TemplateResponse(request, "admin/settings.html", _ctx(
        request, current=sources_repo.all_settings()))


@router.post("/settings")
def settings_save(request: Request, csrf: str = Form("", alias="_csrf"), **form):
    sess = require_role("admin")(request)
    verify_csrf(request, csrf)
    allowed = {"auto_publish_threshold", "manual_review_threshold", "crawl_frequency_minutes",
               "poster_generation", "whatsapp_generation", "candidate_notifications",
               "resume_matching", "job_alerts"}
    for key, value in form.items():
        if key in allowed:
            sources_repo.set_setting(key, str(value))
    _audit(sess["user_id"], "update_settings", "site", None, "", "")
    return RedirectResponse("/admin/settings", status_code=303)


# ---------------------------------------------------------------- reports queue (§69)

@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request):
    require_role(*ADMIN_ROLES)(request)
    rows = db.query_all(
        """SELECT r.*, j.job_title, j.company_name FROM job_reports r
           JOIN jobs j ON j.job_id = r.job_id ORDER BY r.created_at DESC LIMIT 100""")
    return templates.TemplateResponse(request, "admin/reports.html", _ctx(
        request, reports=[dict(r) for r in rows]))


@router.post("/reports/{report_id}/resolve")
def resolve_report(request: Request, report_id: int, status_: str = Form("resolved"),
                   csrf: str = Form("", alias="_csrf")):
    sess = _csrf_guard(request, csrf)
    if status_ not in ("reviewed", "resolved", "dismissed"):
        raise HTTPException(status_code=400, detail="Invalid status")
    db.execute("UPDATE job_reports SET status = ? WHERE report_id = ?", (status_, report_id))
    _audit(sess["user_id"], "resolve_report", "job_report", report_id, status_, "")
    return RedirectResponse("/admin/reports", status_code=303)
