"""Public SSR routes (§5–25, §58–63, §69, §85).

Homepage · jobs · job detail · companies · domains · apply redirector · QR ·
WhatsApp text · poster page · SEO landing pages · sitemap/robots · legal · report job.

NOTE: literal single-segment routes (/jobs/freshers, /jobs/pune, /jobs/search) are
registered BEFORE /jobs/{job_id} so FastAPI doesn't capture them as ints.
"""
from __future__ import annotations

import secrets
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core import database as db
from app.core.config import get_settings
from app.core.security import verify_csrf
from app.repositories import companies_repo, jobs_repo, stats_repo
from app.services import content, freshness, geo, scoring
from app.services.search import JobFilters, parse_filters

settings = get_settings()
router = APIRouter()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def _page_ctx(request: Request, **extra) -> dict:
    sess = request.scope.get("session_data")
    return {"request": request, "session": sess, "active_nav": "", **extra}


def _base_url() -> str:
    return settings.app_base_url.rstrip("/")


# ---------------------------------------------------------------- homepage (§5, §75)

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    stats = stats_repo.platform_stats()
    fresh = jobs_repo.list_jobs(JobFilters(posted_within="24h", per_page=8))[0]
    fresher = jobs_repo.list_jobs(JobFilters(fresher=True, per_page=6))[0]
    radar = stats_repo.placement_radar()
    companies = companies_repo.hiring_companies(8)
    return templates.TemplateResponse(request, "public/home.html", _page_ctx(
        request, stats=stats, fresh_jobs=fresh, fresher_jobs=fresher,
        radar=radar, companies=companies, active_nav="home"))


# ---------------------------------------------------------------- jobs — literal routes first

@router.get("/jobs", response_class=HTMLResponse)
def jobs_list(request: Request):
    f = parse_filters(request.query_params)
    jobs, total = jobs_repo.list_jobs(f)
    pages = max(1, (total + f.per_page - 1) // f.per_page)
    return templates.TemplateResponse(request, "public/jobs.html", _page_ctx(
        request, jobs=jobs, total=total, page=f.page, pages=pages, filters=f,
        posted_filters=freshness.POSTED_FILTERS, active_nav="jobs"))


@router.get("/jobs/search", response_class=HTMLResponse)
def jobs_search(request: Request):
    return jobs_list(request)


@router.get("/jobs/freshers", response_class=HTMLResponse)
def freshers_page(request: Request):
    f = JobFilters(fresher=True, per_page=25)
    jobs, total = jobs_repo.list_jobs(f)
    return templates.TemplateResponse(request, "public/freshers.html", _page_ctx(
        request, jobs=jobs, total=total, active_nav="freshers"))


@router.get("/jobs/pune", response_class=HTMLResponse)
def seo_pune(request: Request):
    return jobs_list(request)


@router.get("/jobs/pune/{topic}", response_class=HTMLResponse)
def seo_pune_topic(request: Request, topic: str):
    topic_map = {
        "freshers": JobFilters(fresher=True),
        "software-developer": JobFilters(q="software developer"),
        "data-analyst": JobFilters(q="data analyst"),
        "cybersecurity": JobFilters(domain="cybersecurity"),
        "devops": JobFilters(domain="devops-cloud"),
        "data-science": JobFilters(domain="data-science-ai-ml"),
        "business-analyst": JobFilters(q="business analyst"),
        "embedded": JobFilters(domain="embedded-iot"),
        "qa": JobFilters(domain="qa-testing"),
        "ai-ml": JobFilters(domain="data-science-ai-ml"),
    }
    f = topic_map.get(topic)
    if not f:
        raise HTTPException(status_code=404, detail="Unknown topic")
    f.per_page = 25
    jobs, total = jobs_repo.list_jobs(f)
    title = topic.replace("-", " ").title() + " Jobs in Pune"
    return templates.TemplateResponse(request, "public/seo_topic.html", _page_ctx(
        request, jobs=jobs, total=total, title=title, topic=topic, active_nav="jobs"))


# ---------------------------------------------------------------- job detail (§13)

def _job_or_404(job_id: int) -> dict:
    job = jobs_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int):
    job = _job_or_404(job_id)
    similar = jobs_repo.similar_jobs(job)
    apply_url = f"{_base_url()}/apply/{job['job_id']}"
    wa_text = content.whatsapp_message(job, apply_url)
    wa_url = f"https://wa.me/?text={quote(wa_text)}"
    mins = freshness.minutes_since(job.get("last_verified_at"))
    verified_band = ("🟢 Open — verified recently" if (mins or 99999) < 60
                     else "🟡 Open — last verified " + freshness.humanize(mins))
    if job["job_status"] in ("expired", "closed"):
        verified_band = "🔴 Application closed"
    return templates.TemplateResponse(request, "public/job_detail.html", _page_ctx(
        request, job=job, similar=similar, apply_url=apply_url, wa_text=wa_text,
        wa_url=wa_url, verified_band=verified_band, active_nav="jobs"))


# ---------------------------------------------------------------- collections (§22)

COLLECTIONS: dict[str, dict] = {
    "todays-best-fresher-jobs": {"title": "🔥 Today's Best Fresher Jobs",
                                 "filters": {"fresher": True, "posted_within": "24h"}},
    "software-developer-jobs-pune": {"title": "💻 Software Developer Jobs — Pune",
                                     "filters": {"q": "software developer", "city": "Pune"}},
    "data-analyst-jobs-pune": {"title": "📊 Data Analyst Jobs — Pune",
                               "filters": {"q": "data analyst", "city": "Pune"}},
    "cybersecurity-jobs": {"title": "🛡 Cybersecurity Jobs",
                           "filters": {"domain": "cybersecurity"}},
    "devops-cloud-jobs": {"title": "☁️ DevOps & Cloud Jobs",
                          "filters": {"domain": "devops-cloud"}},
    "ai-ml-jobs": {"title": "🤖 AI/ML Jobs", "filters": {"domain": "data-science-ai-ml"}},
    "embedded-jobs": {"title": "🔌 Embedded Jobs", "filters": {"domain": "embedded-iot"}},
    "qa-jobs": {"title": "🧪 QA Jobs", "filters": {"domain": "qa-testing"}},
    "0-1-year-jobs": {"title": "🎯 0–1 Year Jobs",
                      "filters": {"experience_max": 1}},
    "jobs-with-salary": {"title": "💰 Jobs with Salary Listed",
                         "filters": {"salary_only": True}},
    "mnc-jobs": {"title": "🏢 MNC Jobs", "filters": {}},
    "startup-jobs": {"title": "🚀 Startup Jobs", "filters": {}},
    "remote-it-jobs": {"title": "🏠 Remote IT Jobs", "filters": {"work_mode": "remote"}},
}


@router.get("/collections/{slug}", response_class=HTMLResponse)
def collection_page(request: Request, slug: str):
    meta = COLLECTIONS.get(slug)
    if not meta:
        raise HTTPException(status_code=404, detail="Collection not found")
    f = JobFilters(per_page=25, **meta["filters"])
    jobs, total = jobs_repo.list_jobs(f)
    return templates.TemplateResponse(request, "public/collection.html", _page_ctx(
        request, jobs=jobs, total=total, title=meta["title"], slug=slug, active_nav="jobs"))


# ---------------------------------------------------------------- companies (§24)

@router.get("/companies", response_class=HTMLResponse)
def companies_page(request: Request, q: str = ""):
    companies = companies_repo.list_companies(q=q)
    return templates.TemplateResponse(request, "public/companies.html", _page_ctx(
        request, companies=companies, q=q, active_nav="companies"))


@router.get("/companies/{slug}", response_class=HTMLResponse)
def company_profile(request: Request, slug: str):
    company = companies_repo.get_company_by_slug(slug)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    counts = companies_repo.company_job_counts(company["company_id"])
    recent = companies_repo.recent_company_jobs(company["company_id"], 6)
    skills = companies_repo.company_top_skills(company["company_id"])
    return templates.TemplateResponse(request, "public/company.html", _page_ctx(
        request, company=company, counts=counts, recent_jobs=recent, top_skills=skills,
        active_nav="companies"))


# ---------------------------------------------------------------- domains (§76)

@router.get("/domains", response_class=HTMLResponse)
def domains_page(request: Request):
    rows = db.query_all(
        """SELECT d.*, COUNT(j.job_id) AS active_jobs FROM domains d
           LEFT JOIN jobs j ON j.domain_id = d.domain_id
             AND j.job_status='active' AND j.verification_status='approved'
             AND j.city IS NOT NULL
           GROUP BY d.domain_id ORDER BY d.sort_order""")
    return templates.TemplateResponse(request, "public/domains.html", _page_ctx(
        request, domains=[dict(r) for r in rows], active_nav="domains"))


@router.get("/domains/{slug}", response_class=HTMLResponse)
def domain_page(request: Request, slug: str):
    row = db.query_one("SELECT * FROM domains WHERE slug = ?", (slug,))
    if not row:
        raise HTTPException(status_code=404, detail="Domain not found")
    domain = dict(row)
    f = JobFilters(domain=slug, per_page=25)
    jobs, total = jobs_repo.list_jobs(f)
    fresher, fresher_total = jobs_repo.list_jobs(JobFilters(domain=slug, fresher=True, per_page=10))
    skills = stats_repo.skill_demand(10, slug)
    return templates.TemplateResponse(request, "public/domain.html", _page_ctx(
        request, domain=domain, jobs=jobs, total=total, fresher_jobs=fresher,
        fresher_total=fresher_total, top_skills=skills, active_nav="domains"))


# ---------------------------------------------------------------- apply redirector (§14)

@router.get("/apply/{job_id}")
def apply_redirect(job_id: int, request: Request):
    job = jobs_repo.get_job(job_id, published_only=False)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    ua = request.headers.get("user-agent", "")
    ua_class = ("mobile" if any(m in ua.lower() for m in ("mobile", "android", "iphone"))
                else "desktop")
    if job["is_demo"]:
        # Demo jobs must never appear to redirect to a real employer (§84).
        return templates.TemplateResponse(request, "public/demo_apply.html", _page_ctx(
            request, job=job), status_code=200)
    if job["job_status"] in ("expired", "closed") or not job.get("application_url"):
        return templates.TemplateResponse(request, "public/apply_closed.html", _page_ctx(
            request, job=job), status_code=410)
    jobs_repo.record_click(job_id, None, "web", ua_class)
    db.execute("UPDATE jobs SET last_verified_at = COALESCE(last_verified_at, ?) WHERE job_id = ?",
               (scoring.now_utc_iso(), job_id))
    return RedirectResponse(job["application_url"], status_code=302)


# ---------------------------------------------------------------- QR + WhatsApp + poster (§15–17)

@router.get("/jobs/{job_id}/qr")
def job_qr(job_id: int, request: Request, format: str = "svg"):
    job = _job_or_404(job_id)
    target = f"{_base_url()}/apply/{job_id}"
    db.execute("INSERT OR IGNORE INTO qr_codes (job_id, target_url) VALUES (?,?)",
               (job_id, target))
    media = "image/svg+xml" if format == "svg" else "image/png"
    data = content.qr_svg(target) if format == "svg" else content.qr_png(target)
    return Response(data, media_type=media)


@router.get("/jobs/{job_id}/whatsapp")
def job_whatsapp(job_id: int, request: Request):
    job = _job_or_404(job_id)
    apply_url = f"{_base_url()}/apply/{job_id}"
    text = content.whatsapp_message(job, apply_url)
    if request.query_params.get("format") == "json":
        return {"text": text, "share_url": f"https://wa.me/?text={quote(text)}"}
    return templates.TemplateResponse(request, "public/whatsapp.html", _page_ctx(
        request, job=job, wa_text=text,
        wa_url=f"https://wa.me/?text={quote(text)}", apply_url=apply_url))


@router.get("/jobs/{job_id}/poster", response_class=HTMLResponse)
def job_poster(request: Request, job_id: int):
    job = _job_or_404(job_id)
    apply_url = f"{_base_url()}/apply/{job_id}"
    return templates.TemplateResponse(request, "public/poster.html", _page_ctx(
        request, job=job, apply_url=apply_url, qr_url=f"/jobs/{job_id}/qr?format=svg",
        active_nav="jobs"))


# ---------------------------------------------------------------- sitemap / robots (§63)

@router.get("/sitemap.xml")
def sitemap():
    base = _base_url()
    urls = ["/", "/jobs", "/jobs/freshers", "/companies", "/domains"]
    urls.extend(f"/collections/{slug}" for slug in COLLECTIONS)
    for topic in ("freshers", "software-developer", "data-analyst", "cybersecurity",
                  "devops", "data-science", "business-analyst", "embedded", "qa", "ai-ml"):
        urls.append(f"/jobs/pune/{topic}")
    rows = db.query_all(
        "SELECT job_id, slug FROM jobs WHERE job_status='active' "
        "AND verification_status='approved' AND city IS NOT NULL "
        "ORDER BY job_id DESC LIMIT 5000")
    urls.extend(f"/jobs/{r['slug']}-{r['job_id']}" for r in rows)
    urls.extend(f"/companies/{r['slug']}" for r in db.query_all("SELECT slug FROM companies"))
    urls.extend(f"/domains/{r['slug']}" for r in db.query_all("SELECT slug FROM domains"))
    today = scoring.now_utc_iso()[:10]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml.append(f"<url><loc>{base}{u}</loc><lastmod>{today}</lastmod></url>")
    xml.append("</urlset>")
    return Response("\n".join(xml), media_type="application/xml")


@router.get("/robots.txt")
def robots():
    body = ("User-agent: *\n"
            "Allow: /\n"
            "Disallow: /apply/\n"
            "Disallow: /admin\n"
            f"Sitemap: {_base_url()}/sitemap.xml\n")
    return Response(body, media_type="text/plain")


# ---------------------------------------------------------------- legal + report (§69, §85)

@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return templates.TemplateResponse(request, "public/privacy.html", _page_ctx(request))


@router.get("/terms", response_class=HTMLResponse)
def terms(request: Request):
    return templates.TemplateResponse(request, "public/terms.html", _page_ctx(request))


@router.get("/disclaimer", response_class=HTMLResponse)
def disclaimer(request: Request):
    return templates.TemplateResponse(request, "public/disclaimer.html", _page_ctx(request))


@router.get("/jobs/{job_id}/report", response_class=HTMLResponse)
def report_form(request: Request, job_id: int):
    job = _job_or_404(job_id)
    existing = request.cookies.get("skillected_csrf")
    token = existing or secrets.token_urlsafe(24)
    response = templates.TemplateResponse(request, "public/report.html", _page_ctx(
        request, job=job, token=token))
    if not existing:
        response.set_cookie("skillected_csrf", token, httponly=True, samesite="lax")
    return response


@router.post("/jobs/{job_id}/report")
def report_submit(request: Request, job_id: int,
                  report_type: str = Form(...), message: str = Form(""),
                  csrf: str = Form("", alias="_csrf")):
    verify_csrf(request, csrf)
    if report_type not in ("incorrect", "expired", "suspicious", "wrong_company",
                           "broken_link", "other"):
        raise HTTPException(status_code=400, detail="Invalid report type")
    db.execute(
        "INSERT INTO job_reports (job_id, report_type, message) VALUES (?,?,?)",
        (job_id, report_type, message[:2000]),
    )
    return RedirectResponse(f"/jobs/{job_id}?reported=1", status_code=303)
