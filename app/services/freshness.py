"""Freshness engine (§7, §86).

Never fabricate posting times: "Posted X ago" only when posting_date_verified;
otherwise "First seen X ago".
"""
from __future__ import annotations

from datetime import datetime, timezone

# Minutes → (emoji label, css_class) exactly per §7 bands.
FRESHNESS_BANDS: list[tuple[int, str, str]] = [
    (30, "🔥 JUST POSTED", "fresh-just"),
    (120, "⚡ VERY FRESH", "fresh-very"),
    (360, "🟢 NEW", "fresh-new"),
    (720, "🔵 RECENT", "fresh-recent"),
    (1440, "🟣 TODAY", "fresh-today"),
    (4320, "RECENT", "fresh-days"),
]
OLDER_LABEL = ("OLDER", "fresh-older")

POSTED_FILTERS: list[tuple[str, int]] = [
    ("30m", 30), ("1h", 60), ("6h", 360), ("12h", 720),
    ("24h", 1440), ("3d", 4320), ("7d", 10080),
]

SORT_OPTIONS: dict[str, tuple[str, str]] = {
    "freshness": ("published_at", "DESC"),      # 1st priority (§7)
    "relevance": ("relevance_rank", "DESC"),    # 2nd priority
    "verification": ("authenticity_score", "DESC"),  # 3rd priority
    "newest": ("first_seen_at", "DESC"),
}


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def minutes_since(value: str | None, now: datetime | None = None) -> float | None:
    dt = parse_dt(value)
    if dt is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 60.0)


def freshness_label(minutes: float | None) -> tuple[str, str]:
    """Return (label, css_class) for an age in minutes (None → OLDER)."""
    if minutes is None:
        return OLDER_LABEL
    for max_min, label, css in FRESHNESS_BANDS:
        if minutes < max_min:
            return label, css
    return OLDER_LABEL


def decorate(job: dict, now: datetime | None = None) -> dict:
    """Add freshness decoration to a job row/dict (§7).

    When the company posting date is verified, both the badge and the label are
    computed from that real date; otherwise everything falls back to first-seen
    and says "First seen" — never "Posted" (§86).
    """
    verified_posting = bool(job.get("posting_date_verified")) and job.get("posting_date")
    basis_value = job.get("posting_date") if verified_posting else None
    age = minutes_since(basis_value or job.get("published_at") or job.get("first_seen_at"), now)
    label, css = freshness_label(age)
    job["freshness_label"] = label
    job["freshness_css"] = css
    job["age_minutes"] = age

    if verified_posting:
        job["time_label"] = f"Posted {humanize(age)}"
        job["time_basis"] = "posted"
    else:
        job["time_label"] = f"First seen {humanize(age)}" if age is not None else ""
        job["time_basis"] = "first_seen"
    return job


def humanize(minutes: float | None) -> str:
    if minutes is None:
        return ""
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{int(minutes)} min ago"
    hours = minutes / 60
    if hours < 24:
        h = int(hours)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    days = int(hours // 24)
    return f"{days} day{'s' if days != 1 else ''} ago"


def live_status(minutes_verified: float | None) -> tuple[str, str]:
    """(§8) → (status text, css class)."""
    if minutes_verified is None:
        return "Open — verification pending", "status-pending"
    if minutes_verified < 60:
        return f"Open — verified {humanize(minutes_verified)}", "status-open"
    if minutes_verified < 1440:
        return f"Open — last verified {humanize(minutes_verified)}", "status-open-recent"
    return "Open — last verified over a day ago", "status-open-stale"
