-- Skillected Jobs — Migration 001: core foundation (companies, sources, jobs, taxonomy, auth)
-- Postgres-ready dialect (see docs/02-DATABASE-DESIGN.md §1).

CREATE TABLE IF NOT EXISTS roles (
    role_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email              TEXT NOT NULL UNIQUE,
    password_hash      TEXT NOT NULL,
    full_name          TEXT,
    is_active          INTEGER NOT NULL DEFAULT 1,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id  INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id  INTEGER NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    csrf_token  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_profiles (
    candidate_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    headline            TEXT,
    experience_years    REAL,
    preferred_locations TEXT,
    preferred_domains   TEXT,
    preferred_roles     TEXT,
    skills              TEXT,
    followed_companies  TEXT,
    salary_preference   TEXT,
    work_mode_pref      TEXT,
    phone               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS companies (
    company_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL UNIQUE,
    slug                TEXT NOT NULL UNIQUE,
    logo_url            TEXT,
    official_url        TEXT,
    careers_url         TEXT,
    industry            TEXT,
    description         TEXT,
    company_size        TEXT,
    hq_location         TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified'
                        CHECK (verification_status IN ('unverified','verified','needs_review','rejected')),
    is_mnc              INTEGER NOT NULL DEFAULT 0,
    is_startup          INTEGER NOT NULL DEFAULT 0,
    is_demo             INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS company_locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    city        TEXT,
    state       TEXT,
    country     TEXT DEFAULT 'India',
    address     TEXT,
    is_hq       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (company_id, city, address)
);

CREATE TABLE IF NOT EXISTS career_sources (
    source_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id               INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    source_url               TEXT NOT NULL,
    source_type              TEXT NOT NULL
                             CHECK (source_type IN ('official_careers','official_ats','permitted_public')),
    ats_type                 TEXT,
    crawl_frequency_minutes  INTEGER NOT NULL DEFAULT 720
                             CHECK (crawl_frequency_minutes IN (15,30,60,360,720,1440)),
    active                   INTEGER NOT NULL DEFAULT 1,
    last_checked_at          TEXT,
    status                   TEXT NOT NULL DEFAULT 'never_checked'
                             CHECK (status IN ('never_checked','healthy','delayed','error','disabled')),
    error_count              INTEGER NOT NULL DEFAULT 0,
    reliability_score        REAL NOT NULL DEFAULT 60.0,
    notes                    TEXT,
    created_at               TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at               TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, source_url)
);

CREATE TABLE IF NOT EXISTS source_runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    INTEGER NOT NULL REFERENCES career_sources(source_id) ON DELETE CASCADE,
    started_at   TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at  TEXT,
    jobs_found   INTEGER NOT NULL DEFAULT 0,
    jobs_new     INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','success','partial','failed')),
    error_text   TEXT
);

CREATE TABLE IF NOT EXISTS domains (
    domain_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    slug         TEXT NOT NULL UNIQUE,
    icon         TEXT,
    description  TEXT,
    sort_order   INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS skill_taxonomy (
    skill_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical     TEXT NOT NULL UNIQUE,
    category      TEXT,
    is_technology INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skill_aliases (
    alias_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id    INTEGER NOT NULL REFERENCES skill_taxonomy(skill_id) ON DELETE CASCADE,
    alias       TEXT NOT NULL,
    alias_lower TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id             INTEGER NOT NULL REFERENCES companies(company_id),
    company_name           TEXT NOT NULL,
    company_logo_url       TEXT,
    job_title              TEXT NOT NULL,
    normalized_job_title   TEXT NOT NULL,
    slug                   TEXT NOT NULL,
    department             TEXT,
    domain_id              INTEGER REFERENCES domains(domain_id),
    sub_domain             TEXT,
    location               TEXT,
    city                   TEXT DEFAULT 'Pune',
    state                  TEXT DEFAULT 'Maharashtra',
    country                TEXT DEFAULT 'India',
    work_mode              TEXT CHECK (work_mode IN ('onsite','hybrid','remote') OR work_mode IS NULL),
    employment_type        TEXT CHECK (employment_type IN ('full_time','part_time','contract','internship') OR employment_type IS NULL),
    experience_min         REAL,
    experience_max         REAL,
    education              TEXT,
    skills                 TEXT,
    technologies           TEXT,
    salary_min             REAL,
    salary_max             REAL,
    salary_currency        TEXT,
    job_description        TEXT,
    requirements           TEXT,
    preferred_skills       TEXT,
    source_type            TEXT CHECK (source_type IN ('official_careers','official_ats','permitted_public') OR source_type IS NULL),
    source_url             TEXT,
    application_url        TEXT,
    official_company_url   TEXT,
    job_requisition_id     TEXT,
    posting_date           TEXT,
    posting_date_verified  INTEGER NOT NULL DEFAULT 0,
    first_seen_at          TEXT NOT NULL DEFAULT (datetime('now')),
    last_verified_at       TEXT,
    deadline               TEXT,
    job_status             TEXT NOT NULL DEFAULT 'active'
                           CHECK (job_status IN ('active','expired','closed','draft')),
    verification_status    TEXT NOT NULL DEFAULT 'pending'
                           CHECK (verification_status IN ('pending','approved','rejected','needs_review')),
    verification_score     REAL,
    authenticity_score     REAL,
    duplicate_hash         TEXT UNIQUE,
    is_fresher_friendly    INTEGER NOT NULL DEFAULT 0,
    is_demo                INTEGER NOT NULL DEFAULT 0,
    published_at           TEXT,
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_city       ON jobs(job_status, city);
CREATE INDEX IF NOT EXISTS idx_jobs_experience        ON jobs(experience_min);
CREATE INDEX IF NOT EXISTS idx_jobs_domain            ON jobs(domain_id);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen        ON jobs(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_published         ON jobs(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_verification      ON jobs(verification_status);
CREATE INDEX IF NOT EXISTS idx_jobs_normalized_title  ON jobs(normalized_job_title);
CREATE INDEX IF NOT EXISTS idx_jobs_demo              ON jobs(is_demo);

CREATE TABLE IF NOT EXISTS job_skills (
    job_id      INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    skill_id    INTEGER NOT NULL REFERENCES skill_taxonomy(skill_id) ON DELETE CASCADE,
    is_required INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (job_id, skill_id)
);

CREATE TABLE IF NOT EXISTS job_sources (
    job_source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    source_id     INTEGER NOT NULL REFERENCES career_sources(source_id),
    source_url    TEXT,
    retrieved_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_verification (
    verification_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id           INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    checked_at       TEXT NOT NULL DEFAULT (datetime('now')),
    method           TEXT,
    url_status       TEXT,
    posting_date_ok  INTEGER,
    availability_ok  INTEGER,
    redirect_safe    INTEGER,
    score            REAL,
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS job_matches (
    match_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                 INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    candidate_id           INTEGER REFERENCES candidate_profiles(candidate_id) ON DELETE SET NULL,
    user_id                INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    job_match_score        REAL,
    candidate_match_score  REAL,
    skill_match_score      REAL,
    experience_match_score REAL,
    location_match_score   REAL,
    education_match_score  REAL,
    explanation            TEXT,
    is_stretch             INTEGER NOT NULL DEFAULT 0,
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (job_id, user_id)
);

CREATE TABLE IF NOT EXISTS application_clicks (
    click_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    user_id    INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    channel    TEXT NOT NULL DEFAULT 'web' CHECK (channel IN ('web','qr','whatsapp')),
    user_agent_class TEXT,
    clicked_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_clicks_job_time ON application_clicks(job_id, clicked_at);

CREATE TABLE IF NOT EXISTS saved_jobs (
    user_id    INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    job_id     INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    saved_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, job_id)
);

CREATE TABLE IF NOT EXISTS job_alerts (
    alert_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    alert_type  TEXT NOT NULL CHECK (alert_type IN ('role','location','domain','skill','company','experience')),
    alert_value TEXT NOT NULL,
    frequency_minutes INTEGER NOT NULL DEFAULT 720
                CHECK (frequency_minutes IN (15,30,60,360,720,1440,10080)),
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT,
    link            TEXT,
    channel         TEXT NOT NULL DEFAULT 'in_app' CHECK (channel IN ('in_app','email','whatsapp','browser')),
    read_at         TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS poster_assets (
    poster_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    width        INTEGER NOT NULL DEFAULT 1080,
    height       INTEGER NOT NULL DEFAULT 1350,
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (job_id, storage_path)
);

CREATE TABLE IF NOT EXISTS qr_codes (
    qr_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    target_url   TEXT NOT NULL,
    storage_path TEXT,
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (job_id, target_url)
);
