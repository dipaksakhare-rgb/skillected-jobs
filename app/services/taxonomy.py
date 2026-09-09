"""Skill taxonomy + alias resolution (§57). Extensible: new aliases are data rows."""
from __future__ import annotations

from app.core import database as db


def resolve_skill(raw: str) -> int | None:
    """Map a raw skill string (or alias) to its canonical skill_id."""
    token = (raw or "").strip().lower()
    if not token:
        return None
    row = db.query_one(
        "SELECT skill_id FROM skill_taxonomy WHERE LOWER(canonical) = ?", (token,)
    )
    if row:
        return int(row["skill_id"])
    row = db.query_one(
        "SELECT skill_id FROM skill_aliases WHERE alias_lower = ?", (token,)
    )
    return int(row["skill_id"]) if row else None


def canonical_name(skill_id: int) -> str | None:
    row = db.query_one("SELECT canonical FROM skill_taxonomy WHERE skill_id = ?", (skill_id,))
    return row["canonical"] if row else None


def normalize_list(raw_skills: list[str]) -> list[tuple[int, str]]:
    """Deduplicate a list of raw skills into [(skill_id, canonical), ...]."""
    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    for raw in raw_skills:
        sid = resolve_skill(raw)
        if sid and sid not in seen:
            seen.add(sid)
            out.append((sid, canonical_name(sid) or raw))
    return out
