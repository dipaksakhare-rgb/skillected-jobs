"""Jobs repository — SQL access only; business rules live in services (§103)."""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager

from app.core import database as db
from app.services import freshness, search as search_svc, scoring
from app.services.search import JobFilters

_LIST_COLS = """j.job_id, j.company_id, j.company_name, j.company_logo_url, j.job_title,
 j.normalized_job_title, j.slug, j.city, j.location, j.state, j.work_mode, j.employment_type,
 j.experience_min, j.experience_max, j.skills, j.salary_min, j.salary_max, j.salary_currency,
 j.domain_id, d.name AS domain_name, d.slug AS domain_slug, d.icon AS domain_icon,
 j.source_type, j.application_url, j.job_status, j.verification_status, j.verification_score,
 j.authenticity_score, j.is_fresher_friendly, j.is_demo, j.posting_date, j.posting_date_verified,
 j.first_seen_at, j.published_at, j.last_verified_at"""


@contextmanager
def _rows_to_dicts(rows) -> Iterator[list[dict]]:
    yield [dict(r) for r in rows]


def _decorate(job: dict) -> dict:
    freshness.decorate(job)
    job["skills_list"] = _parse_json_list(job.get("skills"))
    job["experience_text"] = _experience_text(job)
    job["salary_display"] = _salary_text(job)
    mins = freshness.minutes_since(job.get("last_verified_at"))
    status, css = freshness.live_status(mins)
    if job.get("job_status") in ("expired", "closed"):
        status, css = "Application closed", "status-closed"
    job["live_status"], job["live_status_css"] = status, css
    return job


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return [str(x) for x in val] if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return [s.strip() for s in raw.split(",") if s.strip()]


def _experience_text(job: dict) -> str:
    mn, mx = job.get("experience_min"), job.get("experience_max")
    if mn is None and mx is None:
        return "Not specified"
    if mx is None:
        return f"{_fmt(mn)}+ years"
    return f"{_fmt(mn)}–{_fmt(mx)} years"


def _salary_text(job: dict) -> str:
    mn, mx, cur = job.get("salary_min"), job.get("salary_max"), job.get("salary_currency")
    if mn is None and mx is None:
        return ""
    cur = cur or "INR"
    def money(v):
        return f"{int(v):,}" if v is not None else ""
    if mn is not None and mx is not None:
        return f"{money(mn)} – {money(mx)} {cur}/year"
    if mn is not None:
        return f"From {money(mn)} {cur}/year"
    return f"Up to {money(mx)} {cur}/year"


def _fmt(v: float | None) -> str:
    if v is None:
        return "0"
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


# ---------------------------------------------------------------- query builder

def _where_clause(f: JobFilters, *, published_only: bool = True) -> tuple[str, list]:
    where, params = [], []
    if published_only:
        where.append("j.job_status = 'active'")
        where.append("j.verification_status = 'approved'")
    else:
        where.append("1=1")
    if f.q:
        terms = [f.q] + search_svc.expand_role(f.q)
        conds = []
        for t in terms:
            like = f"%{t}%"
            conds.append(
                "(j.job_title LIKE ? OR j.normalized_job_title LIKE ? "
                "OR j.company_name LIKE ? OR j.skills LIKE ? "
                "OR j.technologies LIKE ?)"
            )
            params.extend([like] * 5)
        where.append("(" + " OR ".join(conds) + ")")
    if f.city:
        where.append("j.city = ?")
        params.append(f.city)
    if f.domain:
        where.append("d.slug = ?")
        params.append(f.domain)
    if f.company:
        where.append("j.company_name LIKE ?")
        params.append(f"%{f.company}%")
    if f.experience_min is not None:
        where.append("COALESCE(j.experience_max, 99) >= ?")
        params.append(f.experience_min)
    if f.experience_max is not None:
        where.append("COALESCE(j.experience_min, 0) <= ?")
        params.append(f.experience_max)
    if f.fresher:
        # Fresher-suitable = explicitly flagged (title tokens) OR a stated min <= 1.
        # Unknown experience is NOT fresher evidence (§30 honesty).
        where.append("(j.is_fresher_friendly = 1 OR j.experience_min <= 1)")
    if f.work_mode:
        where.append("j.work_mode = ?")
        params.append(f.work_mode)
    if f.employment_type:
        where.append("j.employment_type = ?")
        params.append(f.employment_type)
    if f.posted_within:
        minutes = dict((k, v) for k, v in freshness.POSTED_FILTERS).get(f.posted_within)
        if minutes:
            where.append("COALESCE(j.published_at, j.first_seen_at) >= datetime('now', ?)")
            params.append(f"-{int(minutes)} minutes")
    if f.verified_only:
        where.append("j.authenticity_score >= 85")
    if f.salary_only:
        where.append("(j.salary_min IS NOT NULL OR j.salary_max IS NOT NULL)")
    return " AND ".join(where), params


def _order_clause(sort: str) -> str:
    if sort == "verification":
        return "ORDER BY j.authenticity_score DESC, COALESCE(j.published_at, j.first_seen_at) DESC"
    if sort == "relevance":
        return ("ORDER BY j.authenticity_score DESC, COALESCE(j.published_at, j.first_seen_at) DESC, "
                "j.is_fresher_friendly DESC")
    if sort == "newest":
        return "ORDER BY j.first_seen_at DESC"
    return "ORDER BY COALESCE(j.published_at, j.first_seen_at) DESC, j.authenticity_score DESC"


# ---------------------------------------------------------------- public API

def list_jobs(f: JobFilters) -> tuple[list[dict], int]:
    where, params = _where_clause(f)
    base = f"FROM jobs j LEFT JOIN domains d ON d.domain_id = j.domain_id WHERE {where}"
    total = db.query_one(f"SELECT COUNT(*) AS c {base}", tuple(params))["c"]
    offset = (f.page - 1) * f.per_page
    rows = db.query_all(
        f"SELECT {_LIST_COLS} {base} {_order_clause(f.sort)} LIMIT ? OFFSET ?",
        tuple(params) + (f.per_page, offset),
    )
    return [_decorate(dict(r)) for r in rows], int(total)


def get_job(job_id: int, published_only: bool = True) -> dict | None:
    row = db.query_one(
        f"""SELECT j.*, d.name AS domain_name, d.slug AS domain_slug, d.icon AS domain_icon,
             c.official_url AS company_official_url, c.careers_url AS company_careers_url,
             c.verification_status AS company_verification, c.is_mnc, c.is_startup
            FROM jobs j
            LEFT JOIN domains d ON d.domain_id = j.domain_id
            LEFT JOIN companies c ON c.company_id = j.company_id
            WHERE j.job_id = ?""" + (" AND j.job_status='active' AND j.verification_status='approved'"
                                     if published_only else ""),
        (job_id,),
    )
    if not row:
        return None
    job = _decorate(dict(row))
    job["requirements_list"] = _parse_json_list(job.get("requirements"))
    job["preferred_skills_list"] = _parse_json_list(job.get("preferred_skills"))
    job["technologies_list"] = _parse_json_list(job.get("technologies"))
    return job


def similar_jobs(job: dict, limit: int = 6) -> list[dict]:
    rows = db.query_all(
        f"""SELECT {_LIST_COLS} FROM jobs j LEFT JOIN domains d ON d.domain_id = j.domain_id
            WHERE j.job_status='active' AND j.verification_status='approved'
              AND j.job_id != ? AND (j.domain_id = ? OR j.normalized_job_title LIKE ?)
            ORDER BY COALESCE(j.published_at, j.first_seen_at) DESC LIMIT ?""",
        (job["job_id"], job.get("domain_id"), f"%{(job.get('normalized_job_title') or '')[:30]}%", limit),
    )
    return [_decorate(dict(r)) for r in rows]


def record_click(job_id: int, user_id: int | None, channel: str, ua_class: str) -> None:
    db.execute(
        "INSERT INTO application_clicks (job_id, user_id, channel, user_agent_class) VALUES (?,?,?,?)",
        (job_id, user_id, channel, ua_class),
    )


def click_count(job_id: int) -> int:
    row = db.query_one("SELECT COUNT(*) AS c FROM application_clicks WHERE job_id = ?", (job_id,))
    return int(row["c"]) if row else 0


def find_duplicate(company_name: str, normalized_title: str, city: str | None,
                   requisition_id: str | None, application_url: str | None) -> int | None:
    """§49 — return existing job_id with the same duplicate_hash, if any."""
    dhash = scoring.duplicate_hash(company_name, normalized_title, city, requisition_id, application_url)
    row = db.query_one("SELECT job_id FROM jobs WHERE duplicate_hash = ?", (dhash,))
    return int(row["job_id"]) if row else None


# ---------------------------------------------------------------- admin helpers

def admin_list(status: str = "", verification: str = "", q: str = "",
               page: int = 1, per_page: int = 25) -> tuple[list[dict], int]:
    where, params = ["1=1"], []
    if status:
        where.append("j.job_status = ?")
        params.append(status)
    if verification:
        where.append("j.verification_status = ?")
        params.append(verification)
    if q:
        where.append("(j.job_title LIKE ? OR j.company_name LIKE ?)")
        params.extend([f"%{q}%"] * 2)
    wsql = " AND ".join(where)
    total = db.query_one(f"SELECT COUNT(*) AS c FROM jobs j WHERE {wsql}", tuple(params))["c"]
    rows = db.query_all(
        f"""SELECT {_LIST_COLS}, j.job_description FROM jobs j
            LEFT JOIN domains d ON d.domain_id = j.domain_id
            WHERE {wsql}
            ORDER BY j.first_seen_at DESC LIMIT ? OFFSET ?""",
        tuple(params) + (per_page, (page - 1) * per_page),
    )
    return [_decorate(dict(r)) for r in rows], int(total)


def pending_review_count() -> int:
    row = db.query_one(
        "SELECT COUNT(*) AS c FROM jobs WHERE verification_status = 'needs_review' AND job_status='active'"
    )
    return int(row["c"]) if row else 0
