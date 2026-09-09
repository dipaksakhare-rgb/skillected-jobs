"""Companies repository."""
from __future__ import annotations

from app.core import database as db

_ACTIVE = "j.job_status='active' AND j.verification_status='approved'"


def get_company(company_id: int) -> dict | None:
    row = db.query_one("SELECT * FROM companies WHERE company_id = ?", (company_id,))
    return dict(row) if row else None


def get_company_by_slug(slug: str) -> dict | None:
    row = db.query_one("SELECT * FROM companies WHERE slug = ?", (slug,))
    return dict(row) if row else None


def company_job_counts(company_id: int) -> dict:
    row = db.query_one(          f"""SELECT COUNT(*) AS total,
              SUM(CASE WHEN is_fresher_friendly=1 OR experience_min<=1 THEN 1 ELSE 0 END) AS fresher,
              SUM(CASE WHEN experience_min>1 THEN 1 ELSE 0 END) AS experienced
            FROM jobs j WHERE j.company_id = ? AND {_ACTIVE}""",
        (company_id,),
    )
    row = row or {"total": 0, "fresher": 0, "experienced": 0}
    return {k: int(row[k] or 0) for k in ("total", "fresher", "experienced")}


def company_top_skills(company_id: int, limit: int = 8) -> list[dict]:
    """Skills from jobs' skills JSON (LIKE-based; job_skills used in Phase 2 ingestion)."""
    rows = db.query_all(
        f"""SELECT js.skill_id, st.canonical, COUNT(*) AS n
            FROM job_skills js JOIN skill_taxonomy st ON st.skill_id = js.skill_id
            JOIN jobs j ON j.job_id = js.job_id
            WHERE j.company_id = ? AND {_ACTIVE}
            GROUP BY js.skill_id ORDER BY n DESC LIMIT ?""",
        (company_id, limit),
    )
    return [dict(r) for r in rows]


def hiring_companies(limit: int = 12) -> list[dict]:
    rows = db.query_all(
        f"""SELECT c.company_id, c.name, c.slug, c.logo_url, c.industry, c.is_mnc, c.is_startup,
              COUNT(j.job_id) AS active_jobs,
              MAX(COALESCE(j.published_at, j.first_seen_at)) AS latest_job_at
            FROM companies c JOIN jobs j ON j.company_id = c.company_id AND {_ACTIVE}
            GROUP BY c.company_id
            ORDER BY active_jobs DESC, latest_job_at DESC LIMIT ?""",
        (limit,),
    )
    return [dict(r) for r in rows]


def list_companies(q: str = "", limit: int = 100) -> list[dict]:
    if q:
        rows = db.query_all(
            f"""SELECT c.*, COUNT(j.job_id) AS active_jobs
                FROM companies c LEFT JOIN jobs j ON j.company_id=c.company_id AND {_ACTIVE}
                WHERE c.name LIKE ? GROUP BY c.company_id
                ORDER BY active_jobs DESC, c.name LIMIT ?""",
            (f"%{q}%", limit),
        )
    else:
        rows = db.query_all(
            f"""SELECT c.*, COUNT(j.job_id) AS active_jobs
                FROM companies c LEFT JOIN jobs j ON j.company_id=c.company_id AND {_ACTIVE}
                GROUP BY c.company_id ORDER BY active_jobs DESC, c.name LIMIT ?""",
            (limit,),
        )
    return [dict(r) for r in rows]


def recent_company_jobs(company_id: int, limit: int = 5) -> list[dict]:
    from app.repositories import jobs_repo
    from app.services.search import JobFilters
    f = JobFilters(per_page=limit)
    where, params = jobs_repo._where_clause(f)
    where += " AND j.company_id = ?"
    params.append(company_id)
    rows = db.query_all(
        f"""SELECT {jobs_repo._LIST_COLS} FROM jobs j
            LEFT JOIN domains d ON d.domain_id = j.domain_id
            WHERE {where} ORDER BY COALESCE(j.published_at, j.first_seen_at) DESC""",
        tuple(params),
    )
    return [jobs_repo._decorate(dict(r)) for r in rows]
