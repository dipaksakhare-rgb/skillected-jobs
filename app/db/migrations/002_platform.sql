-- Skillected Jobs — Migration 002: placement, analytics, moderation, courses, crawl telemetry.

CREATE TABLE IF NOT EXISTS applications (
    application_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    job_id             INTEGER NOT NULL REFERENCES jobs(job_id),
    company_name       TEXT,
    role_title         TEXT,
    applied_on         TEXT,
    status             TEXT NOT NULL DEFAULT 'applied'
                       CHECK (status IN ('saved','applied','assessment','interview_1','interview_2','hr','selected','offer','joined','rejected','withdrawn')),
    notes              TEXT,
    source             TEXT NOT NULL DEFAULT 'direct' CHECK (source IN ('direct','platform_tracked','manual')),
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, job_id)
);

CREATE TABLE IF NOT EXISTS placement_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    application_id  INTEGER REFERENCES applications(application_id) ON DELETE CASCADE,
    from_status     TEXT,
    to_status       TEXT NOT NULL
                    CHECK (to_status IN ('training','resume_ready','eligible_jobs','recommended_jobs','applied','assessment','interview_1','interview_2','hr','selected','joined','rejected')),
    occurred_at     TEXT NOT NULL DEFAULT (datetime('now')),
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS resumes (
    resume_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    file_name     TEXT,
    storage_path  TEXT,
    file_type     TEXT,
    parse_status  TEXT NOT NULL DEFAULT 'pending' CHECK (parse_status IN ('pending','parsed','failed')),
    parsed_json   TEXT,
    health_score  REAL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    consent       INTEGER NOT NULL DEFAULT 0,
    uploaded_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS resume_skills (
    resume_id  INTEGER NOT NULL REFERENCES resumes(resume_id) ON DELETE CASCADE,
    skill_id   INTEGER REFERENCES skill_taxonomy(skill_id),
    skill_name TEXT NOT NULL,
    is_core    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (resume_id, skill_name)
);

CREATE TABLE IF NOT EXISTS resume_projects (
    project_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id    INTEGER NOT NULL REFERENCES resumes(resume_id) ON DELETE CASCADE,
    title        TEXT,
    description  TEXT,
    technologies TEXT,
    link         TEXT
);

CREATE TABLE IF NOT EXISTS courses (
    course_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,
    domain_id       INTEGER REFERENCES domains(domain_id),
    official_url    TEXT,
    description     TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    last_synced_at  TEXT
);

CREATE TABLE IF NOT EXISTS course_skills (
    course_id INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    skill_id  INTEGER NOT NULL REFERENCES skill_taxonomy(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (course_id, skill_id)
);

CREATE TABLE IF NOT EXISTS course_recommendations (
    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    course_id         INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    reason_skills     TEXT,
    reason_text       TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger          TEXT NOT NULL DEFAULT 'scheduled' CHECK (trigger IN ('scheduled','manual','api')),
    started_at       TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at      TEXT,
    status           TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','success','partial','failed')),
    sources_checked  INTEGER NOT NULL DEFAULT 0,
    jobs_discovered  INTEGER NOT NULL DEFAULT 0,
    it_jobs          INTEGER NOT NULL DEFAULT 0,
    pune_jobs        INTEGER NOT NULL DEFAULT 0,
    fresher_jobs     INTEGER NOT NULL DEFAULT 0,
    verified         INTEGER NOT NULL DEFAULT 0,
    duplicates       INTEGER NOT NULL DEFAULT 0,
    rejected         INTEGER NOT NULL DEFAULT 0,
    errors           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS crawl_errors (
    error_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER REFERENCES crawl_runs(run_id) ON DELETE CASCADE,
    source_id   INTEGER REFERENCES career_sources(source_id) ON DELETE SET NULL,
    source_url  TEXT,
    error_text  TEXT,
    http_status INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    category    TEXT,
    occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admin_actions (
    action_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   INTEGER,
    details     TEXT,
    ip_address  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_admin_actions_time ON admin_actions(created_at DESC);

CREATE TABLE IF NOT EXISTS job_reports (
    report_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      INTEGER NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    report_type TEXT NOT NULL CHECK (report_type IN ('incorrect','expired','suspicious','wrong_company','broken_link','other')),
    message     TEXT,
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','reviewed','resolved','dismissed')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    entity_type TEXT,
    entity_id   INTEGER,
    payload     TEXT,
    processed   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS site_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration   TEXT PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
