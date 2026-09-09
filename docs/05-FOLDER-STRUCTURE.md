# Skillected Jobs — Folder Structure & Run Guide

## Layout

```
skillected-jobs/
├─ app/
│  ├─ __init__.py            create_app factory
│  ├─ core/                  config, database, security (auth/csrf/rate-limit), logging
│  ├─ db/                    schema.sql, migrations/, seed_demo_data.py
│  ├─ repositories/          jobs, companies, sources, skills, stats, events, users
│  ├─ services/              freshness, scoring, duplicates, search, domains, events, content
│  ├─ routers/               public pages, JSON api, admin pages
│  ├─ templates/             Jinja2 (public + admin)
│  └─ static/                css, js, logos
├─ docs/                     architecture documents (§106 outputs)
├─ scripts/                  apply_migrations, run_dev, migrate_sqlite_to_postgres
├─ tests/                    pytest suite
├─ data/                     SQLite file (git-ignored)
├─ requirements.txt
├─ pytest.ini
└─ .env.example
```

## Run (development)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (bash: source .venv/Scripts/activate)
pip install -r requirements.txt
python scripts/apply_migrations.py        # create schema
python app/db/seed_demo_data.py           # seed labeled DEMO data
python scripts/run_dev.py                 # http://127.0.0.1:8000
```

Admin: `/admin/login` — seeded `admin / ChangeMe!Admin1` (development credential,
change in production). All seeded jobs/companies render a **DEMO DATA** badge and are
excluded from public statistics, per §84.

## Conventions

- TypeScript-style strictness in Python: pydantic models + mypy-friendly hints.
- Services (business rules) never import SQL; repositories never contain business rules.
- Every external provider (LLM, queue, storage, WhatsApp) goes behind an interface in
  `app/services/providers/` so it can be swapped without app rewrites (§106).
