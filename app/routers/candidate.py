"""Candidate routes (§29–39, §43–45, §91–93) — resume match, profile, tracking."""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core import database as db
from app.core.config import get_settings
from app.core.security import (client_ip, create_session, destroy_session, get_session,
                               hash_password, limiter, verify_csrf, verify_password)
from app.repositories import candidate_repo, companies_repo, jobs_repo, users_repo
from app.services import freshness, matching, resume_parser

settings = get_settings()
router = APIRouter()
templates = Jinja2Templates(directory=str(settings.templates_dir))

MAX_UPLOAD = 5 * 1024 * 1024
ALLOWED_EXT = (".pdf", ".docx", ".txt")


def _ctx(request: Request, **extra) -> dict:
    sess = request.scope.get("session_data")
    unread = candidate_repo.unread_notifications(sess["user_id"]) if sess else []
    return {"request": request, "session": sess, "active_nav": "",
            "notifications": unread, **extra}


def _require_login(request: Request) -> dict:
    sess = get_session(request)
    if not sess:
        raise HTTPException(status_code=401, detail="Login required")
    return sess


def _login_redirect(request: Request) -> RedirectResponse:
    nxt = request.url.path
    return RedirectResponse(f"/login?next={nxt}", status_code=303)


# ---------------------------------------------------------------- auth (§66)

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/profile"):
    if get_session(request):
        return RedirectResponse(next, status_code=303)
    return templates.TemplateResponse(request, "public/login.html",
                                      _ctx(request, next=next, error="", mode="login"))


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...),
                 next: str = Form("/profile")):
    ip = client_ip(request)
    if not limiter.check("login", ip, 10, 300):
        raise HTTPException(status_code=429, detail="Too many attempts; try later")
    user = users_repo.get_user_by_email(email.strip())
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            request, "public/login.html", _ctx(request, next=next, mode="login",
                                               error="Invalid email or password."),
            status_code=401)
    token, _ = create_session(user["user_id"])
    resp = RedirectResponse(next if next.startswith("/") else "/profile", status_code=303)
    resp.set_cookie(settings.session_cookie, token, httponly=True, samesite="lax",
                    secure=settings.is_prod)
    return resp


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if get_session(request):
        return RedirectResponse("/profile", status_code=303)
    return templates.TemplateResponse(request, "public/login.html",
                                      _ctx(request, next="/profile", error="", mode="register"))


@router.post("/register")
def register_submit(request: Request, email: str = Form(...), password: str = Form(...),
                    full_name: str = Form("")):
    ip = client_ip(request)
    if not limiter.check("register", ip, 6, 600):
        raise HTTPException(status_code=429, detail="Too many attempts; try later")
    email = email.strip().lower()
    if "@" not in email or len(password) < 8:
        return templates.TemplateResponse(
            request, "public/login.html",
            _ctx(request, next="/profile", mode="register",
                 error="Enter a valid email; password must be 8+ characters."),
            status_code=400)
    if users_repo.get_user_by_email(email):
        return templates.TemplateResponse(
            request, "public/login.html", _ctx(request, next="/profile", mode="register",
                                               error="An account with this email exists."),
            status_code=409)
    uid = users_repo.create_user(email, hash_password(password), full_name[:100],
                                 roles=["viewer"])
    token, _ = create_session(uid)
    resp = RedirectResponse("/profile", status_code=303)
    resp.set_cookie(settings.session_cookie, token, httponly=True, samesite="lax",
                    secure=settings.is_prod)
    return resp


@router.get("/logout")
def logout(request: Request):
    destroy_session(request)
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(settings.session_cookie)
    return resp


# ---------------------------------------------------------------- resume match (§29–34)

def _candidate_profile_from_request(request: Request, form_fields: dict | None = None) -> tuple[dict, int | None]:
    """Build a candidate dict from the logged-in profile + optional form fields."""
    sess = get_session(request)
    if not sess:
        raise HTTPException(status_code=401, detail="Login required")
    profile = candidate_repo.get_profile(sess["user_id"]) or {}
    candidate = {
        "skills": [s.strip() for s in (profile.get("skills") or "").split(",") if s.strip()],
        "years_experience": profile.get("experience_years") or 0.0,
        "preferred_locations": profile.get("preferred_locations") or "",
        "preferred_domains": profile.get("preferred_domains") or "",
        "headline": profile.get("headline") or "",
        "job_titles": [t.strip() for t in (profile.get("preferred_roles") or "").split(",") if t.strip()],
    }
    return candidate, sess["user_id"]


@router.get("/resume-match", response_class=HTMLResponse)
def resume_match_page(request: Request):
    sess = get_session(request)
    if not sess:
        # Guests can upload and see matches instantly (results are not stored).
        existing = request.cookies.get("skillected_csrf")
        token = existing or secrets.token_urlsafe(24)
        response = templates.TemplateResponse(request, "public/resume_match.html",
                                              _ctx(request, mode="upload", guest=True,
                                                   csrf_token=token, error=""))
        if not existing:
            response.set_cookie("skillected_csrf", token, httponly=True, samesite="lax")
        return response
    # Existing active resume → show stored results
    row = db.query_one(
        """SELECT * FROM resumes WHERE user_id = ? AND is_active = 1
           ORDER BY resume_id DESC LIMIT 1""", (sess["user_id"],))
    if not row:
        return templates.TemplateResponse(request, "public/resume_match.html",
                                          _ctx(request, mode="upload"))
    parsed = json.loads(row["parsed_json"] or "{}")
    candidate, _ = _candidate_profile_from_request(request)
    candidate["skills"] = parsed.get("skills") or candidate["skills"]
    if parsed.get("years_experience") is not None:
        candidate["years_experience"] = parsed.get("years_experience")
    matches = matching.jobs_for_candidate(candidate, user_id=sess["user_id"])
    gap = matching.skill_gap(candidate["skills"])
    courses = matching.recommend_courses([g["skill"] for g in gap["market_needs"][:6]])
    _health, good, needs = resume_parser.health_score(parsed)
    return templates.TemplateResponse(request, "public/resume_match.html", _ctx(
        request, mode="results", resume=dict(row), parsed=parsed,
        matches=matches, gap=gap, courses=courses, good=good, needs=needs))


@router.post("/resume-match")
async def resume_match_upload(request: Request, resume: UploadFile = File(...),
                              consent: str = Form(""),
                              csrf: str = Form("", alias="_csrf")):
    sess = get_session(request)  # guests allowed — results rendered, never stored
    ip = client_ip(request)
    if not limiter.check("resume_upload", ip, 10, 3600):
        raise HTTPException(status_code=429, detail="Too many uploads; try again later")
    verify_csrf(request, csrf)
    if not consent:
        return templates.TemplateResponse(
            request, "public/resume_match.html",
            _ctx(request, mode="upload", guest=not sess,
                 csrf_token=request.cookies.get("skillected_csrf", ""), error="Consent is required to process your resume."),
            status_code=400)
    if not (resume.filename or "").lower().endswith(ALLOWED_EXT):
        return templates.TemplateResponse(
            request, "public/resume_match.html",
            _ctx(request, mode="upload", guest=not sess,
                 csrf_token=request.cookies.get("skillected_csrf", ""), error="Unsupported file. Use PDF, DOCX or TXT."),
            status_code=400)
    data = await resume.read()
    if len(data) > MAX_UPLOAD:
        return templates.TemplateResponse(
            request, "public/resume_match.html",
            _ctx(request, mode="upload", guest=not sess,
                 csrf_token=request.cookies.get("skillected_csrf", ""), error="File too large (max 5 MB)."), status_code=413)
    try:
        text = resume_parser.extract_text(data, resume.filename or "")
    except Exception:  # noqa: BLE001 — parse failures must not leak internals
        text = ""
    if len(text.strip()) < 40:
        return templates.TemplateResponse(
            request, "public/resume_match.html",
            _ctx(request, mode="upload", guest=not sess,
                 csrf_token=request.cookies.get("skillected_csrf", ""), error="Could not read text from this file. Try a text-based PDF or TXT."),
            status_code=422)
    parsed = resume_parser.parse_resume(text)
    health, good, needs = resume_parser.health_score(parsed)

    if not sess:
        # GUEST: compute everything in memory; store nothing (§65 minimal collection).
        candidate = {
            "skills": parsed.get("skills") or [],
            "years_experience": parsed.get("years_experience") or 0.0,
            "preferred_locations": "Pune",
            "preferred_domains": "",
            "headline": parsed.get("summary") or "",
            "job_titles": [],
        }
        matches = matching.jobs_for_candidate(candidate, user_id=None)
        gap = matching.skill_gap(candidate["skills"])
        courses = matching.recommend_courses([g["skill"] for g in gap["market_needs"][:6]])
        return templates.TemplateResponse(request, "public/resume_match.html", _ctx(
            request, mode="results", guest=True, resume={"health_score": health,
                                                         "file_name": resume.filename},
            parsed=parsed, matches=matches, gap=gap, courses=courses,
            good=good, needs=needs), status_code=200)

    # secure storage (§65, §66): sanitized name under data/resumes/{user}/
    safe_name = Path(resume.filename or "resume").name
    store_dir = settings.data_dir / "resumes" / str(sess["user_id"])
    store_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(safe_name).suffix
    path = store_dir / f"resume-{sess['user_id']}-{abs(hash(safe_name)) % 100000}{suffix}"
    path.write_bytes(data)

    db.execute("UPDATE resumes SET is_active = 0 WHERE user_id = ?", (sess["user_id"],))
    resume_parser.store_resume(sess["user_id"], safe_name, Path(safe_name).suffix.lstrip("."),
                               parsed, health, str(path), consent=bool(consent))
    from app.services import events
    events.emit("RESUME_UPLOADED", "user", sess["user_id"], {"health": health})
    return RedirectResponse("/resume-match", status_code=303)


# ---------------------------------------------------------------- profile (§91, §93)

@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    sess = get_session(request)
    if not sess:
        return _login_redirect(request)
    profile = candidate_repo.get_profile(sess["user_id"])
    saved_ids = candidate_repo.saved_jobs(sess["user_id"])
    saved = [jobs_repo.get_job(jid) for jid in saved_ids[:12]]
    saved = [j for j in saved if j]
    apps = candidate_repo.my_applications(sess["user_id"])
    alerts = candidate_repo.list_alerts(sess["user_id"])
    followed = candidate_repo.followed_companies(sess["user_id"])
    companies = [companies_repo.get_company(cid) for cid in followed[:12]]
    companies = [c for c in companies if c]
    return templates.TemplateResponse(request, "public/profile.html", _ctx(
        request, profile=profile, saved_jobs=saved, applications=apps, alerts=alerts,
        followed_companies=companies, active_nav="profile"))


@router.post("/profile")
async def profile_update(request: Request, csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    form = await request.form()
    fields = {}
    for key in ("headline", "preferred_locations", "preferred_domains", "preferred_roles",
                "skills", "salary_preference", "work_mode_pref", "phone"):
        val = str(form.get(key) or "").strip()[:400]
        if val:
            fields[key] = val
    exp_raw = str(form.get("experience_years") or "").strip()
    try:
        fields["experience_years"] = float(exp_raw) if exp_raw else 0.0
    except ValueError:
        fields["experience_years"] = 0.0
    candidate_repo.upsert_profile(sess["user_id"], **fields)
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/pipeline")
def pipeline_update(request: Request, stage: str = Form(...), csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    try:
        candidate_repo.set_pipeline_stage(sess["user_id"], stage)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid stage")
    return RedirectResponse("/profile", status_code=303)


# ---------------------------------------------------------------- saved jobs / watchlist

@router.post("/jobs/{job_id}/save")
def save_job(request: Request, job_id: int, csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    candidate_repo.save_job(sess["user_id"], job_id)
    return RedirectResponse(request.headers.get("referer") or "/profile", status_code=303)


@router.post("/jobs/{job_id}/unsave")
def unsave_job(request: Request, job_id: int, csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    candidate_repo.unsave_job(sess["user_id"], job_id)
    return RedirectResponse(request.headers.get("referer") or "/profile", status_code=303)


@router.post("/companies/{company_id}/follow")
def follow_company(request: Request, company_id: int, csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    candidate_repo.follow_company(sess["user_id"], company_id)
    return RedirectResponse(request.headers.get("referer") or "/companies", status_code=303)


@router.post("/companies/{company_id}/unfollow")
def unfollow_company(request: Request, company_id: int, csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    candidate_repo.unfollow_company(sess["user_id"], company_id)
    return RedirectResponse(request.headers.get("referer") or "/companies", status_code=303)


# ---------------------------------------------------------------- alerts (§39)

@router.post("/alerts")
async def create_alert(request: Request, csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    form = await request.form()
    alert_type = str(form.get("alert_type") or "role")
    if alert_type not in ("role", "location", "domain", "skill", "company", "experience"):
        raise HTTPException(status_code=400, detail="Invalid alert type")
    freq = int(str(form.get("frequency_minutes") or "720"))
    if freq not in (15, 30, 60, 360, 720, 1440, 10080):
        freq = 720
    candidate_repo.create_alert(sess["user_id"], alert_type,
                                str(form.get("alert_value") or "")[:120], freq)
    return RedirectResponse("/profile", status_code=303)


@router.post("/alerts/{alert_id}/deactivate")
def deactivate_alert(request: Request, alert_id: int, csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    candidate_repo.deactivate_alert(sess["user_id"], alert_id)
    return RedirectResponse("/profile", status_code=303)


# ---------------------------------------------------------------- application tracking (§44)

@router.post("/apply/{job_id}/track")
async def track_application(request: Request, job_id: int, csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    form = await request.form()
    did_apply = str(form.get("did_apply") or "") == "yes"
    if did_apply:
        candidate_repo.add_application(sess["user_id"], job_id,
                                       applied_on=str(form.get("applied_on") or "")[:10] or None,
                                       status="applied", notes=str(form.get("notes") or "")[:500])
    return RedirectResponse(f"/jobs/{job_id}?tracked=1", status_code=303)


@router.post("/applications/{application_id}/status")
def update_application(request: Request, application_id: int, status: str = Form(...),
                       csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    try:
        candidate_repo.update_application_status(sess["user_id"], application_id, status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")
    return RedirectResponse("/profile", status_code=303)


# ---------------------------------------------------------------- notifications

@router.post("/notifications/read")
def notifications_read(request: Request, csrf: str = Form("", alias="_csrf")):
    sess = _require_login(request)
    verify_csrf(request, csrf)
    candidate_repo.mark_notifications_read(sess["user_id"])
    return RedirectResponse(request.headers.get("referer") or "/profile", status_code=303)
