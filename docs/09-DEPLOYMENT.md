# Deploying Skillected Jobs online

This is a live **Python server** (FastAPI + SQLite + background crawler), so it needs
an app host — not a static host like Netlify. The same code that runs in your Preview
tab runs unchanged on any of the hosts below.

## Step 0 — Put the code on GitHub (required by every host)

```bash
git init
git add .
git commit -m "Skillected Jobs — initial release"
```

Then create a **private** repository on github.com and push:

```bash
git remote add origin https://github.com/<your-username>/skillected-jobs.git
git push -u origin main
```

`.gitignore` already excludes `data/` (database, resumes) and `.env` — no secrets or
personal data will be uploaded. The host builds its own database from migrations.

## Recommended: Render.com (easiest, free tier available)

1. Push to GitHub (Step 0).
2. On render.com: **New → Blueprint**, connect the repo — `render.yaml` in this repo
   pre-configures the service, persistent disk and health check.
3. In the dashboard, set the `sync: false` env vars:
   - `ADMIN_EMAIL` — your real email
   - `ADMIN_PASSWORD` — a strong password (the dev default is rejected by deploy_check)
   - `APP_BASE_URL` — `https://<your-app>.onrender.com` (after first deploy reveals the name)
4. Deploy. First boot applies migrations and seeds reference data automatically.

**Free-tier caveat:** free services sleep after ~15 min idle; the first request then
takes ~30 s to wake. The paid starter plan (~$7/mo) stays always-on, which matters
because the crawl scheduler only runs while the app is awake.

## Alternative: Railway.app

1. Push to GitHub (Step 0).
2. railway.new → **Deploy from GitHub repo** → select the repo.
3. Add environment variables (same list as above; Railway injects `PORT` automatically).
4. For persistence, add a **Volume** mounted at `/app/data` (keeps SQLite + resumes).

## Alternative: Fly.io (Docker)

```bash
fly launch --dockerfile Dockerfile    # detects the Dockerfile in this repo
fly secrets set APP_ENV=production APP_SECRET=$(openssl rand -hex 32) \
    ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='<strong>' \
    APP_BASE_URL=https://<your-app>.fly.dev
fly volumes create skillected_data --size 1    # then add to fly.toml: [mounts] source="skillected_data" destination="/app/data"
fly deploy
```

## Pre-deploy checklist

Run locally before pushing:

```bash
python scripts/deploy_check.py     # must print "ready to deploy"
python -m pytest                   # 75 tests must pass
```

In production, `APP_ENV=production` enforces: HSTS header, secure session cookies,
and `deploy_check` rejects the default admin password.

## After first deploy

1. Log in at `https://<your-app>/admin` with the `ADMIN_EMAIL`/`ADMIN_PASSWORD` you set.
2. **Change the password immediately** (Admin → Settings) if your host couldn't keep it secret.
3. First boot auto-registers the 12 real sources and starts an initial crawl
   (`AUTO_REGISTER_SOURCES=1`, `INITIAL_CRAWL=1` are preset in `render.yaml`).
   Jobs land in two buckets: ~800 auto-published (ATS boards with posting dates) and
   ~760 in **Admin → Jobs review queue** (Wipro sitemap + Ashby jobs without posting
   dates — the §54 threshold sends them to manual review). Approve them there; it is
   one batch action and every approval is audit-logged.
4. Verify `/healthz` returns `{"status": "ok"}` and `/sitemap.xml` lists job pages.

## Why not Netlify/Vercel?

Netlify/Vercel host static files or serverless functions. This app needs a persistent
process (background crawl scheduler), a writable filesystem (SQLite, resume uploads)
and long-running sessions — none of which serverless platforms provide. If you want
Netlify in the stack anyway, a common pattern is Netlify serving the marketing pages
and Render/Fly serving the app on `jobs.your-domain.com`.
