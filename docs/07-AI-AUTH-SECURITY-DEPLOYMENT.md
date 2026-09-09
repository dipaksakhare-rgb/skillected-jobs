# Skillected Jobs — AI, Auth, Security & Deployment Architecture

## 1. AI architecture (§55–56, Phase 4)

- **Provider abstraction**: `AIProvider` interface with structured-output method
  `extract(json_schema, prompt, payload) -> dict`. Adapters: OpenAI-compatible, Azure
  OpenAI, self-hosted. Selected via env `AI_PROVIDER` (§106: replaceable without rewrites).
- **Structured extraction schema** (§55): job fields with `null` for unknown — the model
  must never invent company, date, salary, or URL.
- **Division of authority (§56)**: AI does resume parsing, semantic matching, skill
  normalization, classification, summarization, skill-gap analysis. Deterministic code
  owns application URL, posting date, job status, company identity, duplicate detection,
  verification, expiry, source reliability.
- Matching weights (§32): skills 35 · experience 20 · title similarity 15 · education 10 ·
  location 10 · tech stack 5 · domain 5. Output bands 90+/80+/70+/60+/<60, always with a
  human-readable explanation (§33) and stretch opportunities (§34).

## 2. Authentication architecture (§66)

- PBKDF2-HMAC-SHA256, 200 000 iterations, 16-byte random salt, constant-time verify.
- Sessions: opaque 32-byte token → `sessions` table; HttpOnly; SameSite=Lax; Secure in
  prod; sliding 7-day user expiry, 8-hour admin expiry; revoke on logout.
- RBAC: `admin` > `placement_officer` > `viewer`; enforced per-route via dependency.
- CSRF: per-session token, double-submit cookie+form on all POST routes.
- Rate limiting: sliding-window per (IP, route-class) — login 10/5min, forms 30/5min,
  API 120/min (prod: Redis backend).

## 3. Security architecture (§66)

- Parameterized SQL everywhere; no string-built queries.
- Jinja2 autoescape ON; no `|safe` on user content.
- Security headers: CSP, X-Content-Type-Options, Referrer-Policy, X-Frame-Options, HSTS in prod.
- Upload hardening (Phase 4): extension + magic-byte checks, size cap, randomized
  storage names, isolated bucket, antivirus hook, never web-served directly.
- Audit: `admin_actions` (who, what, target, before/after JSON, when, IP).
- Secrets only via environment (`.env` git-ignored); no keys in code or logs.
- Error responses never leak stack traces or SQL.

## 4. Privacy architecture (§65)

Consent before resume upload · private storage (no public URLs) · deletion endpoints for
resume and account · documented retention · minimal collection · apply-click logs carry
no PII (job id, timestamp, coarse UA class) · candidate data never sold.

## 5. Deployment architecture (§79, §103)

- **Phase 1 (local)**: Uvicorn single process, SQLite WAL, `.env`, seed script, pytest.
- **Prod target**: Docker Compose/K8s — `app` container, `postgres`, `redis`,
  `worker` (crawler/queues), object storage for resumes/posters, reverse proxy with TLS,
  secrets via orchestrator env, healthchecks `/healthz`, structured logs, error monitoring.
- CI: lint → typecheck → tests → build image → deploy staging → smoke tests.
