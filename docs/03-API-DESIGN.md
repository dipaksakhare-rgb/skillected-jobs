# Skillected Jobs — API Design (§81)

Base: `/api` (JSON). Pages are server-rendered SSR routes (SEO §63). Errors:
`{"error": {"code, message}}` with proper HTTP status. All list endpoints accept
`page`, `per_page` (≤50) and return `{items, total, page, per_page, pages}`.

## 1. Public JSON API

| Method & path | Purpose |
|---|---|
| `GET /api/jobs` | Filter/sort/paginate jobs. Filters: `q, city, domain, experience_min/max, fresher, work_mode, employment_type, company, posted_within, verified_only, sort` |
| `GET /api/jobs/{job_id}` | Single job (published only) |
| `GET /api/jobs/latest` | Newest published (`hours` param) |
| `GET /api/jobs/freshers` | Fresher-friendly jobs |
| `GET /api/jobs/search` | `q` + filters (same semantics as /jobs page) |
| `GET /api/companies` | Companies with live job counts |
| `GET /api/companies/{slug}` | Company profile + recent jobs |
| `GET /api/domains` | Domain taxonomy with counts |
| `GET /api/skills` | Canonical skill taxonomy + demand counts |
| `GET /api/stats` | Real platform statistics (§6) — demo rows excluded |
| `GET /api/placement-radar` | Pune Placement Radar aggregation (§25) |

## 2. Apply + tracking

| Path | Purpose |
|---|---|
| `GET /apply/{job_id}` | Log click (consented) → 302 to verified official application URL; 410 if expired |
| `GET /jobs/{job_id}/qr` | Server-rendered QR (SVG/PNG) pointing at `/apply/{job_id}` |
| `GET /jobs/{job_id}/whatsapp` | Generated WhatsApp text (§17) |
| `GET /jobs/{job_id}/poster` | Generated poster page (§16) |

## 3. Admin API (session + RBAC + CSRF)

| Method & path | Purpose |
|---|---|
| `POST /api/admin/crawl` | Trigger ingestion run (Phase 2) |
| `POST /api/admin/jobs/{id}/verify` | Approve/verify job |
| `POST /api/admin/jobs/{id}/reject` | Reject job |
| `POST /api/admin/jobs/{id}/expire` | Mark expired (§48) |
| `POST /api/admin/jobs/{id}/application-url` | Replace application URL (§67) |
| `POST /api/admin/jobs/{id}/generate-poster` | Regenerate poster (§67) |
| `POST /api/admin/jobs/{id}/generate-whatsapp` | Regenerate WhatsApp message (§67) |
| `GET/PATCH /api/admin/sources/{id}` | Source registry CRUD + health (§50) |
| `PATCH /api/admin/settings` | Automation settings (§68) |
| `GET /api/admin/metrics` | Dashboard metrics (§41) |

## 4. Candidate API (Phase 4–6, schema-ready)

`POST /api/resumes` · `POST /api/resume-match` · `GET /api/recommendations` ·
`POST /api/applications` · `PATCH /api/applications/{id}`

## 5. Conventions

- Versioning: `/api/v1` prefix reserved; unversioned paths alias v1.
- Auth: session cookie (browser) — API keys reserved for machine clients (§66).
- Pagination: `page`/`per_page`; sorting via whitelisted `sort` values only.
- IDs: integer PKs; public URLs use slug-id form `/jobs/{slug}-{id}` (§13).
- OpenAPI: FastAPI auto-generates `/docs` for the JSON API.
