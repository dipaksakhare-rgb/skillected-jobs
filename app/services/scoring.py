"""Deterministic scoring systems — AI never computes these (§56).

- authenticity_score   §9  (0–100, threshold-gated publication §54)
- source reliability    §10 (tier-based base + error adjustments)
- opportunity score     §21/§90 (no fabricated applicant counts)
- duplicate_hash        §49 (company + normalized title + city + requisition + app URL)
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

SOURCE_TIER_BASE: dict[str, float] = {
    "official_careers": 95.0,  # Tier 1
    "official_ats": 85.0,      # Tier 2
    "permitted_public": 60.0,  # Tier 3
}

VERIFICATION_STATUS_SCORE: dict[str, float] = {
    "approved": 10.0, "pending": 4.0, "needs_review": 0.0, "rejected": 0.0,
}

ATS_TYPES: set[str] = {
    "workday", "greenhouse", "lever", "smartrecruiters", "successfactors",
    "oracle_recruiting", "ashby", "icims", "taleo",
}

FRAUD_PATTERNS: list[tuple[str, float, str]] = [
    ("registration fee", 35.0, "payment_request"),
    ("paytm", 25.0, "payment_request"),
    ("upi id", 25.0, "payment_request"),
    ("security deposit", 35.0, "payment_request"),
    ("training fee", 35.0, "payment_request"),
    ("gmail.com", 20.0, "personal_email"),
    ("yahoo.com", 15.0, "personal_email"),
    ("whatsapp group", 15.0, "suspicious_content"),
    ("send your password", 50.0, "credential_request"),
]

AGGREGATOR_HOSTS: set[str] = {
    "naukri.com", "indeed.com", "linkedin.com", "glassdoor.com", "foundit.in",
    "shine.com", "timesjobs.com", "internshala.com",
}


def authenticity_score(job: dict, source_reliability: float | None = None) -> tuple[float, list[str]]:
    """Compute (score, flags[]) from deterministic signals only (§9)."""
    score = 40.0
    flags: list[str] = []

    if job.get("source_type") in SOURCE_TIER_BASE:
        score += (SOURCE_TIER_BASE[job["source_type"]] - 60.0) * 0.4
    rel = source_reliability if source_reliability is not None else 60.0
    score += (min(max(rel, 0.0), 100.0) - 60.0) * 0.2

    app_url = (job.get("application_url") or "").strip()
    if app_url.startswith("https://"):
        score += 8.0
    elif app_url.startswith("http://"):
        score += 2.0
    else:
        flags.append("missing_application_url")
        score -= 15.0

    if job.get("official_company_url"):
        score += 4.0
    if job.get("job_requisition_id"):
        score += 5.0
    if job.get("posting_date") and job.get("posting_date_verified"):
        score += 6.0
    elif job.get("posting_date"):
        score += 2.0
    if job.get("last_verified_at"):
        score += 4.0

    if job.get("verification_status") == "approved":
        score += VERIFICATION_STATUS_SCORE["approved"]
    elif job.get("verification_status") == "pending":
        score += VERIFICATION_STATUS_SCORE["pending"]

    blob = " ".join(str(job.get(k) or "") for k in
                    ("job_title", "job_description", "application_url", "company_name")).lower()
    for pattern, penalty, flag in FRAUD_PATTERNS:
        if pattern in blob:
            score -= penalty
            flags.append(flag)

    host = _host_of(app_url)
    if host and any(host == a or host.endswith("." + a) for a in AGGREGATOR_HOSTS):
        score -= 30.0
        flags.append("aggregator_application_url")

    return round(min(max(score, 0.0), 100.0), 1), flags


def _host_of(url: str) -> str:
    if not url:
        return ""
    part = url.split("//", 1)[-1].split("/", 1)[0].lower()
    return part[4:] if part.startswith("www.") else part


def source_reliability(source: dict) -> float:
    """§10: tier base, minus error pressure, clamped 0–100."""
    base = SOURCE_TIER_BASE.get(source.get("source_type") or "", 60.0)
    if (source.get("ats_type") or "").lower() in ATS_TYPES and source.get("source_type") == "official_ats":
        base = max(base, 85.0)
    errors = min(source.get("error_count") or 0, 10)
    score = base - errors * 1.5
    override = source.get("reliability_override")
    return round(min(max(override if override is not None else score, 0.0), 100.0), 1)


def publish_decision(score: float, auto_threshold: float = 85.0, review_threshold: float = 70.0) -> str:
    """§54: >= auto → auto publish; >= review → manual review; else reject."""
    if score >= auto_threshold:
        return "auto_publish"
    if score >= review_threshold:
        return "manual_review"
    return "reject"


def opportunity_score(job: dict, minutes_since_published: float | None,
                      fresher_eligible: bool = False, skill_alignment: float = 0.0,
                      location_match: bool = False) -> tuple[float, str, list[str]]:
    """§21/§90 — freshness, eligibility, alignment, openness. NEVER applicant counts."""
    if minutes_since_published is None:
        minutes_since_published = 999999.0
    parts: list[str] = []
    score = 0.0
    if minutes_since_published <= 1440:
        score += 30 * (1 - minutes_since_published / 1440) + 5
        parts.append("posted within 24 hours")
    if job.get("job_status") == "active":
        score += 15
        parts.append("application currently open")
    if job.get("authenticity_score") is not None and job["authenticity_score"] >= 85:
        score += 15
        parts.append("highly trusted source")
    if fresher_eligible:
        score += 10
        parts.append("fresher friendly")
    score += min(max(skill_alignment, 0.0), 20.0)
    if skill_alignment >= 50:
        parts.append("strong profile match")
    if location_match:
        score += 10
        parts.append("location match")
    score = min(round(score, 1), 100.0)
    if score >= 70:
        band, emoji = "HIGH OPPORTUNITY — APPLY EARLY", "🔥"
    elif score >= 45:
        band, emoji = "GOOD OPPORTUNITY", "🟢"
    else:
        band, emoji = "STANDARD OPPORTUNITY", "⚪"
    return score, f"{emoji} {band}", parts


def duplicate_hash(company_name: str, normalized_title: str, city: str | None,
                   requisition_id: str | None, application_url: str | None) -> str:
    """§49 — stable content hash; NULL-ish parts normalize to empty strings."""
    def norm(v: str | None) -> str:
        return " ".join((v or "").lower().split())
    payload = "|".join([
        norm(company_name), norm(normalized_title), norm(city),
        norm(requisition_id), norm(application_url),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
