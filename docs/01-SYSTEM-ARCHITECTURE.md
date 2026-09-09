# Skillected Jobs — System Architecture

## 1. Stack (user-approved adaptation of §79)

| Layer | Choice | Rationale |
|---|---|---|
| Backend | **Python 3.12 + FastAPI** | Runs in the available environment; ASGI, typed, modular |
| UI | **Server-rendered Jinja2 + mobile-first CSS** | Mobile-first (§60), SEO-friendly (§63), zero build step |
| DB (dev) | **SQLite (WAL)** | Zero-setup local dev |
| DB (prod) | **PostgreSQL** | Schema written Postgres-ready (see 01-DATABASE) |
| Auth | server-side sessions (signed cookie + DB store), PBKDF2-SHA256 | No external deps |
| Validation | pydantic | Strong typing at boundaries |
| Migrations | plain `.sql` applied in order (runner included) | Portable SQLite→Postgres |
| Tests | pytest | §83 |

Future phases slot in without redesign: crawler workers (Python/Scrapy, §51), Redis +
BullMQ-style queue (worker abstraction), S3-compatible storage (storage provider), LLM
provider (AI provider layer, §106), server-side QR/poster rendering (§15–16).

## 2. High-level topology

```
[Company career sources]
        │  (Phase 2: crawler workers, API→RSS→HTML→browser-automation ladder)
        ▼
[Ingestion pipeline: parse → normalize → classify → dedupe → verify → score → publish]
        ▼
[PostgreSQL/SQLite] ──► [FastAPI app]
                          ├─ Public SSR pages (jobs, companies, domains, SEO)
                          ├─ JSON API (/api/*)
                          ├─ Apply redirector /apply/{job_id} → official URL
                          ├─ Admin dashboard (RBAC)
                          └─ Event outbox → notifications/alerts/analytics (§88)
```

## 3. Application layering (repository pattern, §103)

```
app/
├─ core/        config, database, security (hashing, CSRF, rate limit), logging
├─ db/          schema.sql, migrations/, seed_demo_data.py
├─ repositories/ data access only (jobs, companies, sources, skills, stats, events, users)
├─ services/    freshness, scoring, duplicates, search, domain taxonomy, event bus
├─ routers/     public pages, api, admin pages
├─ templates/   Jinja2 (base, public, admin)
└─ static/      CSS, JS, logos
```

Services never touch SQL; repositories never contain business rules. Routers orchestrate.

## 4. Request flow — job listing (the 5-second rule, §104)

1. `GET /jobs?...` → `jobs_repo.list_jobs(filters)` (SQL-level filter/sort/paginate).
2. Service layer decorates each row: freshness label, live status, opportunity band.
3. Template renders card: company · role · where · experience · skills · freshness ·
   verification · **APPLY DIRECTLY**.

## 5. Apply flow (§14)

`GET /apply/{job_id}` → log click (consented, UA/IP minimal) → 302 → verified
`application_url`. QR codes reuse the same tracking URL. Final destination is always the
company's page. `robots.txt` disallows `/apply/` for crawlers.

## 6. Event outbox (§88)

`events` table + in-process `EventBus`. Phase-1 events: `JOB_PUBLISHED`, `JOB_EXPIRED`,
`JOB_DISCOVERED`, `APPLICATION_CLICKED`, `QR_SCANNED`, `JOB_ALERT_TRIGGERED`,
`RESUME_UPLOADED`. Phase 3+ moves delivery to a queue worker without changing producers.

## 7. Crawler/source architecture (§50–52, Phase 2)

`career_sources` registry (source_id, company_id, url, type, ATS type, crawl_frequency,
active, last_checked, status, error_count, reliability_score). Access ladder:
**API → RSS → HTML extraction → browser automation only where permitted**. Hard rules:
respect robots.txt, ToS, rate limits; never bypass CAPTCHA/auth/anti-bot/paywalls.
Frequency is per-source data, never hard-coded (§89): 12 h default today, 15 min–24 h
supported by design. Each run writes a `crawl_runs` row + `crawl_errors` log (§53, §82);
per-source failure never breaks the whole system.

## 8. AI architecture (§55–56, Phase 4)

Provider-agnostic `AIProvider` interface (structured JSON output). Used for: resume
parsing, semantic matching, skill normalization, classification, summarization, skill
gaps. **Never** for: application URL, posting date, job status, company identity,
duplicates, verification, expiry. Missing fields must be `null` — never invented.

## 9. Authentication architecture (§66)

- Passwords: PBKDF2-HMAC-SHA256, 200k iterations, per-user salt, constant-time compare.
- Sessions: opaque token (secrets.token_urlsafe 32B) in DB `sessions`, HttpOnly
  SameSite=Lax cookie; expiry sliding 7 days; admin sessions 8 h.
- RBAC: roles `admin`, `placement_officer`, `viewer`; decorators per route.
- CSRF: double-submit token on every state-changing form.
- Rate limiting: in-memory sliding window per IP+route (prod: Redis).

## 10. Deployment architecture (§79, §103)

Phase 1: single Uvicorn process, SQLite WAL, `.env` config, seed script, pytest suite.
Prod target: Docker (app + Postgres + Redis + worker), object storage for resumes/posters,
reverse proxy TLS, secrets via environment only, privacy-conscious analytics.

## 11. Security architecture (§66)

Input validation (pydantic + typed query models) · parameterized SQL only · CSRF tokens ·
XSS-safe templating (Jinja autoescape) · secure file upload path (Phase 4: type sniffing,
size caps, isolated storage, no public URLs) · audit log (`admin_actions`) · rate limits ·
secrets only via env · no API keys in repo · security headers (CSP, X-Content-Type-Options,
Referrer-Policy, X-Frame-Options).

## 12. Privacy architecture (§65)

Resumes are sensitive: consent checkbox, private storage, account/resume deletion,
retention policy, minimal collection, no resume URLs public, no selling candidate data.
Apply-click logging stores only job id, timestamp, coarse UA class — no PII.
