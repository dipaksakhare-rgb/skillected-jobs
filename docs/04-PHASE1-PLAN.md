# Skillected Jobs — Phase 1 Implementation Plan

Scope: **PHASE 1 — FOUNDATION** (§101), with schema seams for Phases 2–7.

## Deliverables

| # | Deliverable | Spec refs |
|---|---|---|
| 1 | Docs: product/system/DB/API/crawler/AI/auth/security/deployment/folder structure | §106 |
| 2 | DB: 30+ table schema, migrations runner, indexes, FKs, demo seed | §78, §84 |
| 3 | Auth: sessions, PBKDF2, RBAC (admin / placement_officer / viewer), CSRF, rate limit | §66 |
| 4 | Jobs: listings, detail, search, filters, freshness labels, sorting | §5–7, §12–13, §58–59 |
| 5 | Direct application: `/apply/{id}` redirector, click tracking, QR, WhatsApp text, poster page | §14–17 |
| 6 | Companies: profiles, watchlist-ready registry | §24 |
| 7 | Domains: career domain pages | §1, §76 |
| 8 | Stats + Placement Radar from real data (demo-excluded) | §6, §25 |
| 9 | Admin dashboard: metrics, review queue, bulk actions, sources, settings | §40–42, §67–68 |
| 10 | SEO: sitemap, robots, JobPosting JSON-LD, meta/OG tags, landing pages | §63 |
| 11 | Legal pages + disclaimer | §85 |
| 12 | Tests: services, repos, routers, auth, apply redirect, dedupe | §83 |
| 13 | Mobile-first UI with APPLY DIRECTLY prominence | §60, §74, §104 |

## Phase-1 out of scope (schema-seamed for later)

Crawler execution (2) · WhatsApp/poster/QR automation services (3) · resume upload +
AI matching (4) · alerts/watchlist feeds (5) · placement pipeline UI (6) · trends (7).

## Acceptance checklist

- [ ] `python scripts/apply_migrations.py` creates schema on a fresh checkout.
- [ ] `python app/db/seed_demo_data.py` seeds labeled DEMO data; nothing unlabeled.
- [ ] All stats/radar pages render only real DB aggregates (never fabricated).
- [ ] Freshness labels match §7 time bands; "first seen" never called "posted" unless verified.
- [ ] `/apply/{id}` redirects to the stored official URL only; demo jobs get a demo interstitial.
- [ ] Admin review queue actions (approve/reject/expire/bulk) work and are audit-logged.
- [ ] pytest suite green; typecheck of app package clean.
- [ ] Mobile viewport: primary CTA visible without scrolling on job cards/detail.
