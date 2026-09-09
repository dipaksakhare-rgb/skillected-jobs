-- Migration 004: operator reliability override for career sources.
--
-- §10/§54: an operator who has manually verified a source (e.g. official ATS
-- boards whose feeds carry no posting dates) can pin its reliability score so
-- its jobs auto-publish instead of piling into the review queue on every crawl.
-- NULL = no override (default behavior); recorded in admin_actions by callers.
ALTER TABLE career_sources ADD COLUMN reliability_override REAL;
