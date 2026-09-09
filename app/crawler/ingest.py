"""Ingestion pipeline (§52): FETCH → PARSE → NORMALIZE → CLASSIFY → DUPLICATE CHECK
→ VERIFY → SCORE → PUBLISH, plus per-source telemetry and the §53 crawl report.

Deterministic systems control verification/scoring/publication (§56); the crawler
never fabricates posting times (§7) and never auto-publishes suspicious jobs (§47).
"""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from app.core import database as db
from app.core.config import get_settings
from app.crawler.fetcher import Fetcher
from app.crawler.providers import ProviderError, detect_city, resolve_provider
from app.repositories import sources_repo
from app.services import scoring
from app.services.taxonomy import normalize_list

log = logging.getLogger("skillected.crawler")

settings = get_settings()

# ---------------------------------------------------------------- classification

DOMAIN_RULES: list[tuple[str, list[str]]] = [
    ("full-stack", ["full stack", "fullstack", "software engineer", "software developer",
                    "frontend", "front-end", "backend", "back-end", "web developer",
                    "react", "node", "java developer", "python developer", "mern",
                    "javascript", "typescript", ".net", "php developer", "django",
                    "spring boot", "angular", "vue"]),
    ("data-science-ai-ml", ["data scientist", "machine learning", "ml engineer",
                            "ai engineer", "generative ai", "genai", "nlp",
                            "computer vision", "deep learning", "mlops",
                            "ai research", "llm", "data science"]),
    ("data-analytics", ["data analyst", "bi analyst", "business intelligence",
                        "reporting analyst", "power bi", "tableau", "analytics",
                        "data visualization", "etl"]),
    ("business-analysis", ["business analyst", "functional analyst", "product analyst",
                           "process analyst", "requirements analyst", "product owner"]),
    ("devops-cloud", ["devops", "cloud engineer", "sre", "site reliability",
                      "platform engineer", "kubernetes", "docker", "terraform",
                      "aws", "azure", "gcp", "ci/cd", "jenkins", "cloud support"]),
    ("cybersecurity", ["cybersecurity", "cyber security", "soc analyst", "security analyst",
                       "security engineer", "vapt", "penetration", "ethical hacking",
                       "appsec", "cloud security", "incident response", "siem",
                       "information security", "grc"]),
    ("embedded-iot", ["embedded", "firmware", "iot engineer", "autosar", "rtos",
                      "stm32", "automotive", "microcontroller", "device driver"]),
    ("qa-testing", ["qa engineer", "software tester", "automation tester", "sdet",
                    "test engineer", "quality assurance", "qa analyst", "selenium",
                    "playwright", "cypress"]),
]

FRESHER_TOKENS = ["fresher", "graduate", "trainee", "intern", "apprentice", "junior",
                  "associate", "entry level", "get", "campus"]


def classify_domain(title: str, description: str = "") -> str | None:
    blob = f"{title} {description[:600]}".lower()
    best_slug, best_score = None, 0
    for slug, keywords in DOMAIN_RULES:
        score = sum(1 for kw in keywords if kw in blob)
        if score > best_score:
            best_slug, best_score = slug, score
    return best_slug


def normalize_job_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip()).lower()


def parse_experience(title: str, description: str) -> tuple[float | None, float | None]:
    """Extract explicit experience bounds; None when absent (never invent, §55)."""
    blob = f"{title} {description[:800]}"
    m = re.search(r"(\d+)\s*(?:-|–|to)\s*(\d+)\s*(?:\+)?\s*(?:years?|yrs?)", blob, re.I)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(\d+)\s*\+\s*(?:years?|yrs?)", blob, re.I)
    if m:
        return float(m.group(1)), None
    if re.search(r"\bfresher\b|\bentry[- ]level\b|\b0\s*years?\b", blob, re.I):
        return 0.0, 1.0
    return None, None


def detect_work_mode(text: str) -> str | None:
    low = text.lower()
    if "remote" in low:
        return "remote"
    if "hybrid" in low:
        return "hybrid"
    if "work from office" in low or "wfo" in low:
        return "onsite"
    return None


def is_fresher_friendly(title: str, exp_min: float | None) -> bool:
    low = title.lower()
    return any(t in low for t in FRESHER_TOKENS) or (exp_min is not None and exp_min <= 1)


# ---------------------------------------------------------------- pipeline

def _due_sources(source_ids: list[int] | None = None) -> list[dict]:
    if source_ids:
        marks = ",".join("?" for _ in source_ids)
        rows = db.query_all(
            f"""SELECT s.*, c.name AS company_name, c.slug AS company_slug,
                  c.official_url AS company_official_url
                FROM career_sources s JOIN companies c ON c.company_id = s.company_id
                WHERE s.source_id IN ({marks}) AND s.active = 1""", tuple(source_ids))
        return [dict(r) for r in rows]
    rows = db.query_all(
        """SELECT s.*, c.name AS company_name, c.slug AS company_slug,
              c.official_url AS company_official_url
           FROM career_sources s JOIN companies c ON c.company_id = s.company_id
           WHERE s.active = 1 AND c.is_demo = 0""")
    now = datetime.now(timezone.utc)
    due: list[dict] = []
    for r in rows:
        s = dict(r)
        last = s.get("last_checked_at")
        if not last:
            due.append(s)
            continue
        try:
            checked = datetime.strptime(last[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            due.append(s)
            continue
        if now - checked >= timedelta(minutes=int(s["crawl_frequency_minutes"] or 720)):
            due.append(s)
    return due


def _domain_id(slug: str | None) -> int | None:
    if not slug:
        return None
    row = db.query_one("SELECT domain_id FROM domains WHERE slug = ?", (slug,))
    return int(row["domain_id"]) if row else None


def _ingest_raw_job(raw: dict, source: dict, reliability: float,
                    auto_threshold: int, review_threshold: int) -> dict:
    """Normalize → classify → dedupe → score → publish one raw job. Returns counters."""
    stats = {"discovered": 0, "new": 0, "duplicates": 0, "rejected": 0, "review": 0,
             "pune": 0, "fresher": 0, "failed": 0}
    title = (raw.get("title") or "").strip()
    url = (raw.get("url") or "").strip()
    if not title or not url:
        return stats
    stats["discovered"] += 1

    company = source["company_name"]
    description = raw.get("description") or ""
    normalized = normalize_job_title(title)
    city = raw.get("city") or detect_city(raw.get("location"))
    exp_min, exp_max = parse_experience(title, description)
    dhash = scoring.duplicate_hash(company, normalized, city, raw.get("requisition_id"), url)
    if db.query_one("SELECT job_id FROM jobs WHERE duplicate_hash = ?", (dhash,)):
        stats["duplicates"] += 1
        return stats

    now_iso = scoring.now_utc_iso()
    posting_date = raw.get("posting_date")
    posting_verified = bool(raw.get("posting_date_verified"))
    work_mode = detect_work_mode(f"{title} {description} {raw.get('location') or ''}")
    fresh = is_fresher_friendly(title, exp_min)

    job_dict = {
        "source_type": source["source_type"],
        "application_url": url,
        "official_company_url": source.get("company_official_url"),
        "job_requisition_id": raw.get("requisition_id"),
        "posting_date": posting_date,
        "posting_date_verified": 1 if posting_verified else 0,
        "last_verified_at": now_iso,
        "verification_status": "pending",
        "company_name": company,
        "job_title": title,
    }
    score, flags = scoring.authenticity_score(job_dict, reliability)

    # §47 fraud gate — suspicious content never auto-publishes.
    fraud_flags = {f for f in flags if f in
                   ("payment_request", "credential_request", "personal_email",
                    "aggregator_application_url")}

    if fraud_flags:
        decision = "manual_review"
    elif score >= auto_threshold:
        decision = "auto_publish"
    elif score >= review_threshold:
        decision = "manual_review"
    else:
        decision = "reject"

    verification_status = {"auto_publish": "approved", "manual_review": "needs_review",
                           "reject": "rejected"}[decision]
    job_status = "active" if decision == "auto_publish" else "draft"

    slug = re.sub(r"[^a-z0-9-]+", "-", f"{normalized}-{city or 'india'}".lower())[:70].strip("-")
    slug = f"{slug}-{dhash[:8]}"
    published_at = now_iso if decision == "auto_publish" else None

    insert_cols = ("company_id, company_name, job_title, normalized_job_title, "
                   "slug, domain_id, location, city, state, work_mode, employment_type, "
                   "experience_min, experience_max, skills, technologies, job_description, "
                   "source_type, source_url, application_url, job_requisition_id, "
                   "posting_date, posting_date_verified, first_seen_at, last_verified_at, "
                   "job_status, verification_status, verification_score, authenticity_score, "
                   "duplicate_hash, is_fresher_friendly, is_demo, published_at")
    placeholders = ", ".join("?" * 32)
    try:
        job_id = db.execute(
            f"INSERT INTO jobs ({insert_cols}) VALUES ({placeholders})",
            (source["company_id"], company, title, normalized, slug,
             _domain_id(classify_domain(title, description)), raw.get("location"), city,
             "Maharashtra" if city and city not in ("Remote",) else None, work_mode, None,
             exp_min, exp_max, None, None, description or None,
             source["source_type"], source["source_url"], url, raw.get("requisition_id"),
             posting_date, 1 if posting_verified else 0, now_iso, now_iso,
             job_status, verification_status, round(score, 1), round(score, 1),
             dhash, 1 if fresh else 0, 0, published_at),
        )
        if source.get("company_official_url"):
            db.execute("UPDATE jobs SET official_company_url = ? WHERE job_id = ?",
                       (source["company_official_url"], job_id))
    except sqlite3.IntegrityError:
        stats["duplicates"] += 1
        return stats

    # skill links via taxonomy (§57) — only tokens the taxonomy already knows.
    skill_tokens = re.split(r"[,;/•\n]", description)[:60]
    mapped = normalize_list([t.strip() for t in skill_tokens if 2 < len(t.strip()) < 40])
    for sid, _canon in mapped:
        db.execute("INSERT OR IGNORE INTO job_skills (job_id, skill_id, is_required) VALUES (?,?,1)",
                   (job_id, sid))

    db.execute(
        """INSERT INTO job_verification (job_id, method, url_status, posting_date_ok,
             availability_ok, redirect_safe, score, notes)
           VALUES (?,?,?,?,?,?,?,?)""",
        (job_id, "source_fetch", "200", 1 if posting_verified else None, 1,
         1 if url.startswith("https://") else 0, round(score, 1),
         ",".join(flags) or None),
    )
    db.execute(
        "INSERT INTO job_sources (job_id, source_id, source_url) VALUES (?,?,?)",
        (job_id, source["source_id"], source["source_url"]),
    )

    from app.services import events
    events.emit("JOB_DISCOVERED", "job", job_id, {"company": company, "title": title})
    if decision == "auto_publish":
        events.emit("JOB_PUBLISHED", "job", job_id, {"company": company, "title": title})
        stats["new"] += 1
        if city == "Pune":
            stats["pune"] += 1
        if fresh:
            stats["fresher"] += 1
    elif decision == "manual_review":
        events.emit("JOB_VERIFIED", "job", job_id, {"score": score})
        stats["review"] += 1
    else:
        stats["rejected"] += 1
    return stats


def _crawl_source(source: dict, fetcher: Fetcher, run_id: int,
                  auto_threshold: int, review_threshold: int) -> dict:
    reliability = scoring.source_reliability(source)
    src_run_id = db.execute(
        "INSERT INTO source_runs (source_id) VALUES (?)", (source["source_id"],))
    totals = {"discovered": 0, "new": 0, "duplicates": 0, "rejected": 0, "review": 0,
              "pune": 0, "fresher": 0, "failed": 0}
    error_text = ""
    try:
        provider = resolve_provider(source, fetcher)
        for raw in provider.fetch_jobs(source):
            r = _ingest_raw_job(raw, source, reliability, auto_threshold, review_threshold)
            for k in totals:
                totals[k] += r[k]
        status, delta = "success", 0.5
    except ProviderError as exc:
        status, delta = "failed", 0.0
        totals["failed"] = 1
        error_text = str(exc)[:500]
        log.warning("source %s failed: %s", source["source_id"], exc)

    errors = max(0, int(source.get("error_count") or 0) + (1 if status == "failed" else 0))
    new_reliability = min(100.0, max(0.0, reliability + (delta if status == "success" else 0)))
    health = "healthy" if status == "success" else "error"
    db.execute(
        """UPDATE career_sources SET last_checked_at = ?, status = ?, error_count = ?,
             reliability_score = ?, updated_at = datetime('now') WHERE source_id = ?""",
        (scoring.now_utc_iso(), health, errors, round(new_reliability, 1), source["source_id"]),
    )
    db.execute(
        """UPDATE source_runs SET finished_at = ?, jobs_found = ?, jobs_new = ?,
             status = ?, error_text = ? WHERE run_id = ?""",
        (scoring.now_utc_iso(), totals["discovered"], totals["new"],
         "success" if status == "success" else "failed", error_text or None, src_run_id),
    )
    if error_text:
        db.execute(
            """INSERT INTO crawl_errors (run_id, source_id, source_url, error_text,
                 category) VALUES (?,?,?,?,?)""",
            (run_id, source["source_id"], source["source_url"], error_text, "provider"),
        )
    return totals


def run_crawl(trigger: str = "manual", source_ids: list[int] | None = None) -> dict:
    """Run one crawl cycle over due (or forced) sources; returns the §53 report."""
    auto_threshold = sources_repo.get_int_setting("auto_publish_threshold", 85)
    review_threshold = sources_repo.get_int_setting("manual_review_threshold", 70)
    sources = _due_sources(source_ids)
    if not sources and trigger == "scheduled":
        # Nothing due — don't create an empty run row (keeps §53 history meaningful).
        return {"run_id": None, "sources": 0, "discovered": 0, "new": 0, "duplicates": 0,
                "rejected": 0, "review": 0, "pune": 0, "fresher": 0, "errors": 0,
                "skipped": True}
    run_id = db.execute(
        'INSERT INTO crawl_runs ("trigger") VALUES (?)', (trigger,))
    fetcher = Fetcher()
    totals = {"run_id": run_id, "sources": 0, "discovered": 0, "new": 0, "duplicates": 0,
              "rejected": 0, "review": 0, "pune": 0, "fresher": 0, "errors": 0, "failed": 0}
    for source in sources:
        totals["sources"] += 1
        r = _crawl_source(source, fetcher, run_id, auto_threshold, review_threshold)
        for k in ("discovered", "new", "duplicates", "rejected", "review", "pune",
                  "fresher", "failed"):
            totals[k] += r.get(k, 0)

    db.execute(
        """UPDATE crawl_runs SET finished_at = ?, status = ?, sources_checked = ?,
             jobs_discovered = ?, it_jobs = ?, pune_jobs = ?, fresher_jobs = ?,
             verified = ?, duplicates = ?, rejected = ?, errors = ? WHERE run_id = ?""",
        (scoring.now_utc_iso(),
         "success" if totals["errors"] == 0 else ("partial" if totals["new"] else "failed"),
         totals["sources"], totals["discovered"], totals["new"], totals["pune"],
         totals["fresher"], totals["new"], totals["duplicates"], totals["rejected"],
         totals["errors"], run_id),
    )
    log.info("crawl complete: %s", totals)
    return totals


# ---------------------------------------------------------------- expiry (§48)

def run_expiry_check(max_jobs: int = 25) -> dict:
    """Re-verify active non-demo jobs whose application URL may have died (§48).

    404/410 → job_status='expired' + JOB_EXPIRED event. Network errors leave the
    job untouched (never expire on our own connectivity problems).
    """
    fetcher = Fetcher(min_interval=1.5)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
    rows = db.query_all(
        """SELECT job_id, application_url, company_name, job_title FROM jobs
           WHERE job_status='active' AND is_demo=0 AND application_url IS NOT NULL
             AND (last_verified_at IS NULL OR last_verified_at < ?)
           ORDER BY COALESCE(last_verified_at, first_seen_at) LIMIT ?""", (cutoff, max_jobs))
    expired = 0
    checked = 0
    for row in rows:
        res = fetcher.fetch(row["application_url"])
        checked += 1
        now_iso = scoring.now_utc_iso()
        if res.status in (404, 410):
            db.execute("UPDATE jobs SET job_status='expired', last_verified_at=?, "
                       "updated_at=? WHERE job_id=?", (now_iso, now_iso, row["job_id"]))
            db.execute("""INSERT INTO job_verification (job_id, method, url_status,
                           availability_ok, score, notes) VALUES (?,?,?,?,?,?)""",
                       (row["job_id"], "http_check", str(res.status), 0, 0,
                        "application url dead"))
            from app.services import events
            events.emit("JOB_EXPIRED", "job", row["job_id"],
                        {"company": row["company_name"], "title": row["job_title"]})
            expired += 1
        elif res.status and res.status < 400:
            db.execute("UPDATE jobs SET last_verified_at=? WHERE job_id=?", (now_iso, row["job_id"]))
        # network error → skip (no false expiry)
    return {"checked": checked, "expired": expired}
