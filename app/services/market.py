"""Market intelligence (§26–27, §70–73) — computed from real platform rows only.

Sample-size guards: insights are suppressed when data is insufficient (§70) —
a trend needs >= 8 jobs in the comparison window; skill lists need >= 5 jobs.
"""
from __future__ import annotations

from app.core import database as db
from app.services import geo

MIN_JOBS_FOR_TREND = 8
MIN_JOBS_FOR_SKILLS = 5


def _active(where_extra: str = "", params: tuple = ()) -> tuple[str, tuple]:
    where = ("j.job_status='active' AND j.verification_status='approved' AND j.is_demo=0"
             f" AND {geo.SCOPE_SQL}")
    if where_extra:
        where += f" AND {where_extra}"
    return where, params


def hiring_trends() -> dict:
    """§26 — 30d vs previous 30d posting volume per domain, with growth labels."""
    rows = db.query_all(
        f"""SELECT d.name, d.slug, d.icon,
              SUM(CASE WHEN COALESCE(j.published_at, j.first_seen_at)
                        >= datetime('now', '-30 days') THEN 1 ELSE 0 END) AS recent,
              SUM(CASE WHEN COALESCE(j.published_at, j.first_seen_at)
                        >= datetime('now', '-60 days')
                    AND COALESCE(j.published_at, j.first_seen_at)
                        < datetime('now', '-30 days') THEN 1 ELSE 0 END) AS previous
            FROM jobs j JOIN domains d ON d.domain_id = j.domain_id
            WHERE {_active()[0]}
            GROUP BY d.domain_id ORDER BY recent DESC""")
    trends = []
    for r in rows:
        recent, previous = int(r["recent"] or 0), int(r["previous"] or 0)
        if recent + previous < MIN_JOBS_FOR_TREND:
            change = None  # insufficient data (§70)
        elif previous == 0:
            change = 100.0
        else:
            change = round((recent - previous) / previous * 100.0, 1)
        label = ("—" if change is None else
                 f"▲ {change:+.0f}%" if change > 0 else
                 f"▼ {change:.0f}%" if change < 0 else "► stable")
        trends.append({"name": r["name"], "slug": r["slug"], "icon": r["icon"],
                       "recent": recent, "previous": previous, "change": change,
                       "label": label})
    return {"trends": trends, "note": ("Trends appear once 8+ jobs span two 30-day windows."
                                       if all(t["change"] is None for t in trends) else "")}


def skill_demand_shift(limit: int = 15) -> dict:
    """§27 — most requested skills + 30d momentum, real job_skills rows only."""
    total = db.query_one(
        f"""SELECT COUNT(DISTINCT j.job_id) AS c FROM jobs j
            WHERE {_active()[0]}""")
    if not total or int(total["c"]) < MIN_JOBS_FOR_SKILLS:
        return {"skills": [], "note": "Skill demand appears once 5+ verified jobs exist."}
    rows = db.query_all(
        f"""SELECT st.canonical,
              SUM(CASE WHEN COALESCE(j.published_at, j.first_seen_at)
                        >= datetime('now', '-30 days') THEN 1 ELSE 0 END) AS recent,
              COUNT(*) AS total
            FROM job_skills js
            JOIN skill_taxonomy st ON st.skill_id = js.skill_id
            JOIN jobs j ON j.job_id = js.job_id
            WHERE {_active()[0]}
            GROUP BY st.skill_id ORDER BY total DESC LIMIT ?""", (limit,))
    skills = [dict(r) for r in rows]
    return {"skills": skills, "total_jobs": int(total["c"]), "note": ""}


def domain_demand(limit: int = 9) -> list[dict]:
    where, _ = _active()
    rows = db.query_all(
        f"""SELECT d.name, d.slug, d.icon, COUNT(j.job_id) AS jobs,
              SUM(CASE WHEN j.is_fresher_friendly=1 OR j.experience_min<=1
                  THEN 1 ELSE 0 END) AS fresher
            FROM jobs j JOIN domains d ON d.domain_id = j.domain_id
            WHERE {where}
            GROUP BY d.domain_id ORDER BY jobs DESC LIMIT ?""", (limit,))
    return [dict(r) for r in rows]


def company_hiring_intelligence(limit: int = 10) -> list[dict]:
    """§46 — openings, fresher share, top role, frequency; only where data exists."""
    where, _ = _active()
    rows = db.query_all(
        f"""SELECT c.name, c.slug,
              COUNT(j.job_id) AS openings,
              SUM(CASE WHEN j.is_fresher_friendly=1 OR j.experience_min<=1
                  THEN 1 ELSE 0 END) AS fresher_openings,
              MAX(COALESCE(j.published_at, j.first_seen_at)) AS latest_posting,
              MIN(COALESCE(j.published_at, j.first_seen_at)) AS earliest_posting
            FROM companies c JOIN jobs j ON j.company_id = c.company_id
            WHERE {where}
            GROUP BY c.company_id
            HAVING openings >= 2
            ORDER BY openings DESC, latest_posting DESC LIMIT ?""", (limit,))
    out = []
    for r in rows:
        top = db.query_one(
            f"""SELECT j.job_title, COUNT(*) AS n FROM jobs j
                WHERE j.company_id = (SELECT company_id FROM companies WHERE slug = ?)
                  AND {where}
                GROUP BY j.normalized_job_title ORDER BY n DESC LIMIT 1""",
            (r["slug"],))
        out.append({**dict(r), "top_role": top["job_title"] if top else None})
    return out


def curriculum_intelligence(min_jobs: int = 3) -> list[dict]:
    """§71 — per-domain top market-requested skills mapped to Skillected courses.

    Answers: 'which skills should the training curriculum emphasize?' Real data only.
    """
    rows = db.query_all(
        f"""SELECT d.name AS domain_name, d.slug AS domain_slug, COUNT(DISTINCT j.job_id) AS jobs
            FROM jobs j JOIN domains d ON d.domain_id = j.domain_id
            WHERE {_active()[0]}
            GROUP BY d.domain_id HAVING jobs >= ? ORDER BY jobs DESC""", (min_jobs,))
    out = []
    for domain in rows:
        skills = db.query_all(
            f"""SELECT st.canonical, COUNT(*) AS demand
                FROM job_skills js
                JOIN skill_taxonomy st ON st.skill_id = js.skill_id
                JOIN jobs j ON j.job_id = js.job_id
                JOIN domains d ON d.domain_id = j.domain_id
                WHERE {_active('d.slug = ?')} AND d.slug = ?
                GROUP BY st.skill_id ORDER BY demand DESC LIMIT 6""",
            (domain["domain_slug"], domain["domain_slug"]))
        courses = db.query_all(
            """SELECT c.title, c.slug FROM courses c
               JOIN domains d ON d.domain_id = c.domain_id
               WHERE d.slug = ? AND c.is_active = 1""", (domain["domain_slug"],))
        out.append({
            "domain_name": domain["domain_name"], "domain_slug": domain["domain_slug"],
            "jobs": int(domain["jobs"]),
            "top_skills": [dict(s) for s in skills],
            "courses": [dict(c) for c in courses],
        })
    return out


def officer_alerts() -> list[dict]:
    """§94 — placement officer alerts from real platform state."""
    alerts: list[dict] = []
    broken = db.query_one(
        "SELECT COUNT(*) AS c FROM career_sources WHERE status='error' AND active=1")
    if broken and int(broken["c"] or 0) > 0:
        alerts.append({"level": "error", "text": f"{broken['c']} career source(s) in error state — check Source Health."})
    stale = db.query_one(
        """SELECT COUNT(*) AS c FROM jobs WHERE job_status='active' AND is_demo=0
           AND (last_verified_at IS NULL OR last_verified_at < datetime('now', '-3 days'))""")
    if stale and int(stale["c"] or 0) > 5:
        alerts.append({"level": "warn", "text": f"{stale['c']} jobs not verified in 3+ days — run expiry check."})
    pending = db.query_one(
        "SELECT COUNT(*) AS c FROM jobs WHERE verification_status='needs_review' AND job_status='active'")
    if pending and int(pending["c"] or 0) > 0:
        alerts.append({"level": "warn", "text": f"{pending['c']} job(s) awaiting manual review."})
    fresher_spike = db.query_one(
        f"""SELECT COUNT(*) AS c FROM jobs j WHERE {_active('j.is_fresher_friendly=1')}
            AND COALESCE(j.published_at, j.first_seen_at) >= datetime('now', '-2 days')""")
    if fresher_spike and int(fresher_spike["c"] or 0) >= 5:
        alerts.append({"level": "info", "text": f"{fresher_spike['c']} fresher-friendly jobs in the last 48h — share with students."})
    return alerts
