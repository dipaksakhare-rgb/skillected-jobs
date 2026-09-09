from datetime import datetime, timedelta, timezone

from app.services import freshness


def test_band_just_posted():
    label, css = freshness.freshness_label(10)
    assert label == "🔥 JUST POSTED" and css == "fresh-just"


def test_band_very_fresh():
    assert freshness.freshness_label(90)[0] == "⚡ VERY FRESH"


def test_band_new():
    assert freshness.freshness_label(200)[0] == "🟢 NEW"


def test_band_recent_6_to_12h():
    assert freshness.freshness_label(500)[0] == "🔵 RECENT"


def test_band_today_12_to_24h():
    assert freshness.freshness_label(900)[0] == "🟣 TODAY"


def test_band_days():
    assert freshness.freshness_label(2 * 1440)[0] == "RECENT"


def test_band_older():
    assert freshness.freshness_label(5 * 1440)[0] == "OLDER"
    assert freshness.freshness_label(None)[0] == "OLDER"


def test_decorate_never_calls_first_seen_posted():
    now = datetime.now(timezone.utc)
    job = {"first_seen_at": (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
           "posting_date_verified": 0}
    freshness.decorate(job, now=now)
    assert job["time_label"].startswith("First seen")
    assert job["time_basis"] == "first_seen"


def test_decorate_verified_posting():
    now = datetime.now(timezone.utc)
    job = {"first_seen_at": (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
           "posting_date": (now - timedelta(minutes=90)).strftime("%Y-%m-%d %H:%M:%S"),
           "posting_date_verified": 1}
    freshness.decorate(job, now=now)
    assert job["time_label"].startswith("Posted")
    assert job["time_basis"] == "posted"
    # badge follows the real posting date (90min → VERY FRESH, not JUST POSTED)
    assert job["freshness_css"] == "fresh-very"


def test_decorate_verified_flag_without_date_falls_back():
    """Cannot say 'Posted' with no date to compute from (§7 honesty)."""
    now = datetime.now(timezone.utc)
    job = {"first_seen_at": (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
           "posting_date": None, "posting_date_verified": 1}
    freshness.decorate(job, now=now)
    assert job["time_label"].startswith("First seen")


def test_humanize():
    assert freshness.humanize(0.5) == "just now"
    assert freshness.humanize(45) == "45 min ago"
    assert freshness.humanize(120) == "2 hours ago"
    assert freshness.humanize(3 * 1440) == "3 days ago"


def test_live_status():
    assert "verified" in freshness.live_status(10)[0]
    assert "last verified" in freshness.live_status(240)[0]
