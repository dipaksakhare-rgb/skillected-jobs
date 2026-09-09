"""Candidate-facing data (Phase 5): profiles, saved jobs, watchlist, alerts, applications."""
from __future__ import annotations

from app.core import database as db


# ---------------------------------------------------------------- profile (§91)

def get_profile(user_id: int) -> dict | None:
    row = db.query_one("SELECT * FROM candidate_profiles WHERE user_id = ?", (user_id,))
    return dict(row) if row else None


def upsert_profile(user_id: int, **fields) -> None:
    allowed = {"headline", "experience_years", "preferred_locations", "preferred_domains",
               "preferred_roles", "skills", "followed_companies", "salary_preference",
               "work_mode_pref", "phone"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            sets.append(f"{k} = ?")
            params.append(v)
    existing = db.query_one("SELECT candidate_id FROM candidate_profiles WHERE user_id = ?", (user_id,))
    if existing:
        if sets:
            db.execute(f"UPDATE candidate_profiles SET {', '.join(sets)}, "
                       "updated_at = datetime('now') WHERE user_id = ?", (*params, user_id))
    else:
        db.execute(
            f"INSERT INTO candidate_profiles (user_id{', ' + ', '.join(sets) if sets else ''}) "
            f"VALUES (?{', ?' * len(sets)})", (user_id, *params))


# ---------------------------------------------------------------- saved jobs (§91)

def save_job(user_id: int, job_id: int) -> None:
    db.execute("INSERT OR IGNORE INTO saved_jobs (user_id, job_id) VALUES (?,?)", (user_id, job_id))


def unsave_job(user_id: int, job_id: int) -> None:
    db.execute("DELETE FROM saved_jobs WHERE user_id = ? AND job_id = ?", (user_id, job_id))


def saved_jobs(user_id: int) -> list[int]:
    return [int(r["job_id"]) for r in db.query_all(
        "SELECT job_id FROM saved_jobs WHERE user_id = ? ORDER BY saved_at DESC", (user_id,))]


# ---------------------------------------------------------------- watchlist (§23)

def follow_company(user_id: int, company_id: int) -> None:
    profile = get_profile(user_id)
    current = _parse_ids(profile.get("followed_companies") if profile else None)
    if company_id not in current:
        current.append(company_id)
        upsert_profile(user_id, followed_companies=",".join(map(str, current)))


def unfollow_company(user_id: int, company_id: int) -> None:
    profile = get_profile(user_id)
    current = _parse_ids(profile.get("followed_companies") if profile else None)
    if company_id in current:
        current.remove(company_id)
        upsert_profile(user_id, followed_companies=",".join(map(str, current)))


def followed_companies(user_id: int) -> list[int]:
    profile = get_profile(user_id)
    return _parse_ids(profile.get("followed_companies") if profile else None)


def _parse_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(x) for x in str(raw).split(",") if x.strip().isdigit()]


# ---------------------------------------------------------------- alerts (§39)

def create_alert(user_id: int, alert_type: str, value: str, frequency_minutes: int = 720) -> int:
    return db.execute(
        """INSERT INTO job_alerts (user_id, alert_type, alert_value, frequency_minutes)
           VALUES (?,?,?,?)""", (user_id, alert_type, value, frequency_minutes))


def deactivate_alert(user_id: int, alert_id: int) -> None:
    db.execute("UPDATE job_alerts SET active = 0 WHERE alert_id = ? AND user_id = ?",
               (alert_id, user_id))


def list_alerts(user_id: int) -> list[dict]:
    return [dict(r) for r in db.query_all(
        "SELECT * FROM job_alerts WHERE user_id = ? AND active = 1 ORDER BY alert_id DESC",
        (user_id,))]


def run_alert_sweep() -> int:
    """§62 — notify watchers of new verified jobs from followed companies."""
    follows = db.query_all(
        """SELECT DISTINCT cp.user_id, cp.followed_companies FROM candidate_profiles cp
           WHERE cp.followed_companies IS NOT NULL AND cp.followed_companies != ''""")
    notified = 0
    for row in follows:
        ids = _parse_ids(row["followed_companies"])
        if not ids:
            continue
        marks = ",".join("?" for _ in ids)
        new_jobs = db.query_all(
            f"""SELECT j.job_id, j.company_name, j.job_title, j.city FROM jobs j
                WHERE j.company_id IN ({marks}) AND j.job_status='active'
                  AND j.verification_status='approved' AND j.is_demo=0
                  AND j.city IS NOT NULL
                  AND j.published_at >= datetime('now', '-24 hours')""",
            tuple(ids))
        for job in new_jobs:
            exists = db.query_one(
                """SELECT 1 FROM notifications WHERE user_id = ? AND event_type =
                   'COMPANY_JOB_POSTED' AND link = ?""",
                (row["user_id"], f"/jobs/{job['job_id']}"))
            if exists:
                continue
            db.execute(
                """INSERT INTO notifications (user_id, event_type, title, body, link, channel)
                   VALUES (?,?,?,?,?,'in_app')""",
                (row["user_id"], "COMPANY_JOB_POSTED",
                 f"🔔 New job from {job['company_name']}",
                 f"{job['job_title']} — {job['city']}. Direct application available.",
                 f"/jobs/{job['job_id']}"))
            notified += 1
    return notified


# ---------------------------------------------------------------- notifications

def unread_notifications(user_id: int) -> list[dict]:
    return [dict(r) for r in db.query_all(
        """SELECT * FROM notifications WHERE user_id = ? AND read_at IS NULL
           ORDER BY created_at DESC LIMIT 20""", (user_id,))]


def mark_notifications_read(user_id: int) -> None:
    db.execute("UPDATE notifications SET read_at = datetime('now') "
               "WHERE user_id = ? AND read_at IS NULL", (user_id,))


# ---------------------------------------------------------------- applications (§43–45)

ALLOWED_STATUSES = ("saved", "applied", "assessment", "interview_1", "interview_2",
                    "hr", "selected", "offer", "joined", "rejected", "withdrawn")

PIPELINE_ORDER = ("training", "resume_ready", "eligible_jobs", "recommended_jobs",
                  "applied", "assessment", "interview_1", "interview_2", "hr",
                  "selected", "joined", "rejected")


def add_application(user_id: int, job_id: int, applied_on: str | None = None,
                    status: str = "applied", notes: str = "") -> int:
    row = db.query_one(
        """SELECT job_title, company_name FROM jobs WHERE job_id = ?""", (job_id,))
    title = row["job_title"] if row else None
    company = row["company_name"] if row else None
    app_id = db.execute(
        """INSERT INTO applications (user_id, job_id, company_name, role_title, applied_on,
             status, notes, source) VALUES (?,?,?,?,?,?,?, 'platform_tracked')
           ON CONFLICT(user_id, job_id) DO UPDATE SET
             status=excluded.status, applied_on=COALESCE(excluded.applied_on, applications.applied_on),
             notes=excluded.notes, updated_at=datetime('now')""",
        (user_id, job_id, company, title, applied_on, status, notes[:1000]))
    record_pipeline_event(user_id, app_id, "applied")
    return app_id


def update_application_status(user_id: int, application_id: int, new_status: str) -> None:
    if new_status not in ALLOWED_STATUSES:
        raise ValueError(f"invalid status {new_status}")
    row = db.query_one("SELECT status FROM applications WHERE application_id = ? AND user_id = ?",
                       (application_id, user_id))
    if not row:
        return
    db.execute("UPDATE applications SET status = ?, updated_at = datetime('now') "
               "WHERE application_id = ?", (new_status, application_id))
    record_pipeline_event(user_id, application_id, new_status)


def my_applications(user_id: int) -> list[dict]:
    return [dict(r) for r in db.query_all(
        """SELECT a.*, j.job_title, j.city, j.slug FROM applications a
           LEFT JOIN jobs j ON j.job_id = a.job_id
           WHERE a.user_id = ? ORDER BY a.updated_at DESC""", (user_id,))]


def record_pipeline_event(user_id: int, application_id: int, to_status: str) -> None:
    mapping = {"applied": "applied", "assessment": "assessment", "interview_1": "interview_1",
               "interview_2": "interview_2", "hr": "hr", "selected": "selected",
               "joined": "joined", "rejected": "rejected"}
    mapped = mapping.get(to_status)
    if not mapped:
        return
    db.execute(
        """INSERT INTO placement_events (user_id, application_id, from_status, to_status)
           SELECT user_id, ?, status, ? FROM applications WHERE application_id = ?""",
        (application_id, mapped, application_id))


def set_pipeline_stage(user_id: int, stage: str) -> None:
    """Manual candidate pipeline stage (§43) — stored as a placement_event trail."""
    if stage not in PIPELINE_ORDER:
        raise ValueError(f"invalid stage {stage}")
    db.execute(
        """INSERT INTO placement_events (user_id, from_status, to_status, notes)
           SELECT user_id, (SELECT to_status FROM placement_events WHERE user_id = ?
             ORDER BY event_id DESC LIMIT 1), ?, 'manual update'""",
        (user_id, stage))
