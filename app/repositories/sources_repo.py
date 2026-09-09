"""Career sources repository (§50) + site settings (§68)."""
from __future__ import annotations

from app.core import database as db


def list_sources(include_inactive: bool = True) -> list[dict]:
    sql = """SELECT s.*, c.name AS company_name, c.slug AS company_slug
             FROM career_sources s JOIN companies c ON c.company_id = s.company_id"""
    if not include_inactive:
        sql += " WHERE s.active = 1"
    sql += " ORDER BY c.name"
    return [dict(r) for r in db.query_all(sql)]


def get_source(source_id: int) -> dict | None:
    row = db.query_one(
        """SELECT s.*, c.name AS company_name FROM career_sources s
           JOIN companies c ON c.company_id = s.company_id WHERE s.source_id = ?""",
        (source_id,),
    )
    return dict(row) if row else None


def create_source(company_id: int, source_url: str, source_type: str,
                  ats_type: str = "", frequency: int = 720) -> int:
    base = {"official_careers": 95.0, "official_ats": 85.0, "permitted_public": 60.0}
    return db.execute(
        """INSERT INTO career_sources
           (company_id, source_url, source_type, ats_type, crawl_frequency_minutes, reliability_score)
           VALUES (?,?,?,?,?,?)""",
        (company_id, source_url, source_type, ats_type, frequency,
         base.get(source_type, 60.0)),
    )


def update_source(source_id: int, **fields) -> None:
    allowed = {"source_url", "source_type", "ats_type", "crawl_frequency_minutes",
               "active", "status", "reliability_score", "reliability_override", "notes"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        return
    sets.append("updated_at = datetime('now')")
    params.append(source_id)
    db.execute(f"UPDATE career_sources SET {', '.join(sets)} WHERE source_id = ?", tuple(params))


def compute_health(source: dict) -> tuple[str, str]:
    """§95 → (status_emoji_label, css)."""
    if not source.get("active"):
        return "⏸ Disabled", "src-disabled"
    status = source.get("status") or "never_checked"
    mapping = {
        "healthy": ("🟢 Healthy", "src-healthy"),
        "delayed": ("🟡 Delayed", "src-delayed"),
        "error": ("🔴 Error", "src-error"),
        "never_checked": ("⚪ Never checked", "src-never"),
    }
    return mapping.get(status, ("⚪ Unknown", "src-never"))


# ---------------------------------------------------------------- site settings

def get_setting(key: str, default: str = "") -> str:
    row = db.query_one("SELECT value FROM site_settings WHERE key = ?", (key,))
    return row["value"] if row and row["value"] is not None else default


def get_int_setting(key: str, default: int) -> int:
    try:
        return int(get_setting(key, str(default)))
    except ValueError:
        return default


def all_settings() -> dict[str, str]:
    return {r["key"]: r["value"] or "" for r in db.query_all(
        "SELECT key, value FROM site_settings ORDER BY key")}


def set_setting(key: str, value: str) -> None:
    db.execute(
        """INSERT INTO site_settings (key, value, updated_at) VALUES (?,?,datetime('now'))
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (key, value),
    )
