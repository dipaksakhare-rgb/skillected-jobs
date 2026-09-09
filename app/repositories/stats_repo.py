"""Stats repository — every number computed from real rows; demo data excluded (§6, §25, §84)."""
from __future__ import annotations

from app.core import database as db
from app.services import geo

_ACTIVE_PUBLISHED = ("job_status='active' AND verification_status='approved' AND is_demo=0"
                     " AND city IS NOT NULL")


def platform_stats() -> dict:
    """§6 live statistics — only real aggregates."""
    def scalar(sql: str, params: tuple = ()) -> int:
        row = db.query_one(sql, params)
        return int(row["c"]) if row and row["c"] is not None else 0

    base = f"SELECT COUNT(*) AS c FROM jobs WHERE {_ACTIVE_PUBLISHED}"
    return {
        "jobs_discovered_today": scalar(
            f"{base} AND COALESCE(published_at, first_seen_at) >= datetime('now', '-1 day')"),
        "jobs_last_12h": scalar(
            f"{base} AND COALESCE(published_at, first_seen_at) >= datetime('now', '-12 hours')"),
        "jobs_last_24h": scalar(
            f"{base} AND COALESCE(published_at, first_seen_at) >= datetime('now', '-24 hours')"),
        "fresher_jobs": scalar(
            f"{base} AND (is_fresher_friendly=1 OR experience_min<=1)"),
        "experienced_jobs": scalar(
            f"{base} AND experience_min>1"),
        "pune_jobs": scalar(f"{base} AND city='Pune'"),
        "maharashtra_jobs": scalar(f"{base} AND state='Maharashtra'"),
        "companies_hiring": scalar(
            f"""SELECT COUNT(DISTINCT j.company_id) AS c FROM jobs j
                WHERE {_ACTIVE_PUBLISHED}"""),
        "verified_openings": scalar(
            f"{base} AND authenticity_score >= 85"),
        "total_active_jobs": scalar(base),
    }


def placement_radar() -> dict:
    """§25 — Domain | New jobs (24h) | Fresher | Experienced, real rows only."""
    rows = db.query_all(
        f"""SELECT d.name, d.slug, d.icon,
              COUNT(*) AS total,
              SUM(CASE WHEN COALESCE(j.published_at, j.first_seen_at)
                        >= datetime('now','-1 day') THEN 1 ELSE 0 END) AS new_jobs,
              SUM(CASE WHEN j.is_fresher_friendly=1 OR j.experience_min<=1
                        THEN 1 ELSE 0 END) AS fresher,
              SUM(CASE WHEN j.experience_min>1 THEN 1 ELSE 0 END) AS experienced
            FROM jobs j JOIN domains d ON d.domain_id = j.domain_id
            WHERE {_ACTIVE_PUBLISHED}
            GROUP BY d.domain_id ORDER BY total DESC"""
    )
    by_domain = [dict(r) for r in rows]
    totals = {
        "new_jobs": sum(int(r["new_jobs"] or 0) for r in by_domain),
        "fresher": sum(int(r["fresher"] or 0) for r in by_domain),
        "experienced": sum(int(r["experienced"] or 0) for r in by_domain),
        "total": sum(int(r["total"] or 0) for r in by_domain),
    }
    return {"by_domain": by_domain, "totals": totals, "generated_at": db.query_one(
        "SELECT datetime('now') AS t")["t"]}


def skill_demand(limit: int = 15, domain_slug: str = "") -> list[dict]:
    """§27 — most requested skills from job_skills links (real rows only)."""
    params: list = []
    where = "j.job_status='active' AND j.verification_status='approved' AND j.is_demo=0" + \
        f" AND {geo.SCOPE_SQL}"
    join = ""
    if domain_slug:
        join = "JOIN domains d ON d.domain_id = j.domain_id"
        where += " AND d.slug = ?"
        params.append(domain_slug)
    rows = db.query_all(
        f"""SELECT st.canonical, st.category, COUNT(*) AS demand
            FROM job_skills js
            JOIN skill_taxonomy st ON st.skill_id = js.skill_id
            JOIN jobs j ON j.job_id = js.job_id {join}
            WHERE {where}
            GROUP BY st.skill_id ORDER BY demand DESC LIMIT ?""",
        tuple(params + [limit]),
    )
    return [dict(r) for r in rows]


def latest_events(limit: int = 10) -> list[dict]:
    return [dict(r) for r in db.query_all(
        "SELECT event_type, entity_type, entity_id, created_at FROM events "
        "ORDER BY created_at DESC LIMIT ?", (limit,))]
