"""JSON API (§81) — public read endpoints; admin endpoints live in the admin router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.repositories import companies_repo, jobs_repo, stats_repo
from app.services import freshness
from app.services.search import JobFilters, parse_filters

router = APIRouter(prefix="/api")


def _paged(items: list, total: int, page: int, per_page: int) -> dict:
    return {"items": items, "total": total, "page": page, "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page)}


@router.get("/jobs")
def api_jobs(request: Request,
             page: int = Query(1, ge=1), per_page: int = Query(20, ge=5, le=50)):
    f = parse_filters(request.query_params)
    f.page, f.per_page = page, per_page
    jobs, total = jobs_repo.list_jobs(f)
    return _paged(jobs, total, f.page, f.per_page)


@router.get("/jobs/latest")
def api_latest(hours: int = Query(24, ge=1, le=168), per_page: int = Query(20, ge=5, le=50)):
    f = JobFilters(posted_within="24h" if hours <= 24 else "7d", per_page=per_page)
    jobs, total = jobs_repo.list_jobs(f)
    return _paged(jobs, total, 1, per_page)


@router.get("/jobs/freshers")
def api_freshers(page: int = Query(1, ge=1), per_page: int = Query(20, ge=5, le=50)):
    f = JobFilters(fresher=True, page=page, per_page=per_page)
    jobs, total = jobs_repo.list_jobs(f)
    return _paged(jobs, total, page, per_page)


@router.get("/jobs/search")
def api_search(request: Request, q: str = Query("", max_length=200),
               page: int = Query(1, ge=1), per_page: int = Query(20, ge=5, le=50)):
    f = parse_filters(request.query_params)
    f.page, f.per_page = page, per_page
    jobs, total = jobs_repo.list_jobs(f)
    return _paged(jobs, total, page, per_page)


@router.get("/jobs/{job_id}")
def api_job(job_id: int):
    job = jobs_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/companies")
def api_companies(q: str = "", limit: int = Query(50, ge=1, le=200)):
    return {"items": companies_repo.list_companies(q=q, limit=limit)}


@router.get("/companies/{slug}")
def api_company(slug: str):
    company = companies_repo.get_company_by_slug(slug)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company["job_counts"] = companies_repo.company_job_counts(company["company_id"])
    company["top_skills"] = companies_repo.company_top_skills(company["company_id"])
    return company


@router.get("/domains")
def api_domains():
    from app.core import database as db
    rows = db.query_all(
        """SELECT d.*, COUNT(j.job_id) AS active_jobs FROM domains d
           LEFT JOIN jobs j ON j.domain_id = d.domain_id
             AND j.job_status='active' AND j.verification_status='approved'
           GROUP BY d.domain_id ORDER BY d.sort_order""")
    return {"items": [dict(r) for r in rows]}


@router.get("/skills")
def api_skills(limit: int = Query(30, ge=1, le=100), domain: str = ""):
    return {"items": stats_repo.skill_demand(limit, domain)}


@router.get("/stats")
def api_stats():
    return stats_repo.platform_stats()


@router.get("/placement-radar")
def api_radar():
    return stats_repo.placement_radar()
