# Run doc — Skillected Jobs (Python FastAPI)

## Production deployment (LIVE)

URL: **https://skillected-jobs.onrender.com** (Render free tier, blueprint from
`render.yaml`, auto-deploys on every push to main). Admin: `/admin` with the
`ADMIN_EMAIL`/`ADMIN_PASSWORD` set in Render's dashboard. Free tier: sleeps after
~15 min idle; DB is ephemeral and rebuilt by the bootstrap on each deploy.

## Reproduce artifacts (fresh checkout)

```bash
python -m pip install -r requirements.txt
python scripts/apply_migrations.py      # creates SQLite schema at data/skillected.db
python app/db/seed_demo_data.py         # seeds labeled DEMO data + admin user + course catalog
```

No `.env` file is required (sensible defaults in `app/core/config.py`); copy
`.env.example` → `.env` to override. Admin login (dev): `admin@skillected.local` /
`ChangeMe!Admin1` → change immediately in production.

## Run the server

```bash
python scripts/run_dev.py 8001          # default 8000 is often busy; 8001 is this thread's port
```

Then open http://127.0.0.1:8001 — homepage, /jobs, /jobs/freshers, /companies,
/domains, /collections/*, /admin (dashboard), /docs (OpenAPI), /sitemap.xml, /robots.txt.

## Real job sources (Phase 2 live)

12 companies publish verified openings via their own official channels — ATS boards
and public careers sitemaps (no aggregators):

- **Greenhouse:** Speechify, Arkose Labs, DigiCert, Orion Innovation, ConnectWise, Securly, Addepar
- **Lever:** Pattern
- **Ashby:** OpenGov, Ontic, CertifyOS
- **Careers sitemap (Radancy):** Wipro (854 Pune + 242 Mumbai; via
  `careers.wipro.com` sitemap — compliant public sitemap, no job pages scraped)

Note: TCS (login-gated portal), Infosys (robots.txt blocks everything), Cognizant
(403s non-browser agents) and Capgemini (public feed has no India roles) are NOT
ingestable compliantly under the §51 rules and were deliberately skipped.
Guests can upload resumes without an account (results rendered in-memory, never
stored); logged-in candidates keep stored resumes and profiles as before.

Manage: `python scripts/register_real_sources.py` (idempotent) ·
crawl now: `python scripts/crawl_once.py [source_id ...]` · probe: `python scripts/probe_sources.py`.
The background scheduler re-crawls each source at its own cadence (6–12 h) and runs the
expiry check. Jobs from these companies are `is_demo=0` and drive every public statistic.

## Background services

The app starts a crawl scheduler thread (polls every 5 min; per-source cadence 15 min–24 h).
It never crawls demo-company sources. Disable with `SKIP_SCHEDULER=1`. Crawl + expiry
runs are also triggerable from **/admin/crawler**.

## Tests

```bash
python -m pytest        # 75 tests — services, crawlers, matching, resume AI, routers, auth
```
