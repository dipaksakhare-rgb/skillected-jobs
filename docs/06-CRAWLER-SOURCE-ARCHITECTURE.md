# Skillected Jobs — Crawler & Source Architecture (§50–52)

Implemented in **Phase 2**; Phase 1 ships the registry, schema and run telemetry.

## 1. Source registry (`career_sources`)

```text
source_id · company_id · source_url · source_type · ats_type · crawl_frequency_minutes
active · last_checked_at · status · error_count · reliability_score · notes
```

`source_type ∈ {official_careers, official_ats, permitted_public}`.
ATS registry (verify company identity before trusting, §2): Workday, Greenhouse, Lever,
SmartRecruiters, SAP SuccessFactors, Oracle Recruiting, Ashby, iCIMS, Taleo.

## 2. Access ladder

1. **API first** — official/public recruitment APIs and JSON feeds.
2. **RSS/Atom feeds** second.
3. **HTML extraction** third (career pages, sitemaps).
4. **Browser automation** only where explicitly permitted.

## 3. Compliance rules (hard)

Respect robots.txt, Terms of Service, rate limits, access restrictions, privacy laws and
applicable regulations. **Never** bypass CAPTCHA, authentication, anti-bot protections,
paywalls or access controls. Never circumvent security controls. A source that requires
bypassing any of these is not used.

## 4. Run pipeline (§52)

```
START CRAWL → CHECK SOURCES → FETCH → PARSE → NORMALIZE → CLASSIFY
→ DUPLICATE CHECK → VERIFY → SCORE → PUBLISH → GENERATE POSTER
→ GENERATE QR → GENERATE WHATSAPP → MATCH CANDIDATES → SEND NOTIFICATIONS → STORE ANALYTICS
```

Each run writes `crawl_runs` (discovered, it_jobs, pune_jobs, fresher_jobs, verified,
duplicates, rejected, errors, started/finished, status) and `crawl_errors`
(source, error, timestamp, HTTP status, retry count, error category). One source failing
never aborts the run (§82); failures use capped exponential backoff per source.

## 5. Frequencies (§89 — data, never hard-coded)

Per-source `crawl_frequency_minutes` ∈ {15, 30, 60, 360, 720 (default), 1440}. The
scheduler reads the registry; moving a source from 12-hour to 15-minute is a data change,
not a code change. Alert/notification frequencies (§39) only expose values the ingestion
infrastructure actually supports.

## 6. Health monitoring (§95)

`status ∈ {healthy, delayed, error, disabled}` derived from `last_checked_at`,
`error_count`, and last-run outcome → Source Health board in admin (🟢🟡🔴) with
investigation links into `crawl_errors`.

## 7. Reliability score (§10)

Tier 1 official careers site: base 95 · Tier 2 official ATS: base 85 · Tier 3 permitted
public: base 60. Adjusted by observed error rate and verification outcomes. Admin can
manually override the classification and score.
