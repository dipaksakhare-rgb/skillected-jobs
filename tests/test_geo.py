"""Maharashtra geographic scope (§3) + fresher word-boundary classification."""
from __future__ import annotations

import pytest

from app.crawler.ingest import is_fresher_friendly
from app.crawler.providers import detect_city
from app.services import geo


@pytest.mark.parametrize("text,expected", [
    ("Pune, Maharashtra, India", ("Pune", "Maharashtra")),
    ("Pune, IN", ("Pune", "Maharashtra")),
    ("US | Pune | Hinjewadi", ("Pune", "Maharashtra")),
    ("Hinjewadi Phase 2", ("Pune", "Maharashtra")),
    ("Pimpri, PCMC", ("Pimpri-Chinchwad", "Maharashtra")),
    ("Navi Mumbai, India", ("Navi Mumbai", "Maharashtra")),
    ("Nashik Road", ("Nashik", "Maharashtra")),
    ("Pune, IN; Remote", ("Pune", "Maharashtra")),
    ("Remote - India", ("Remote", None)),
])
def test_in_scope_locations_normalize(text, expected):
    assert geo.normalize_location(text) == expected


@pytest.mark.parametrize("text", [
    "Bangalore, India", "Bengaluru, Karnataka", "Hyderabad, Telangana, India",
    "Gurugram, IN", "New York, NY", "London, UK", "Edinburgh, UK",
    "Cape Town", "Mexico City, Mexico City, Mexico", "Palo Alto, CA, USA",
    "Tokyo, Japan", "Sao Paulo, Brazil", "Warsaw, Poland", "Remote",
    "US | Illinois | Chicago", "Lehi, UT, US (hybrid)", "", None,
])
def test_out_of_scope_locations_are_none(text):
    assert geo.normalize_location(text) is None


def test_detect_city_is_scope_aware():
    assert detect_city("Pune, Maharashtra, India") == "Pune"
    assert detect_city("Bangalore, India") is None
    assert detect_city("Remote - New York, USA") is None
    assert detect_city("Remote - India") == "Remote"


def test_fresher_word_boundaries():
    # 'GET' as a word counts; 'get' inside budget/target must NOT.
    assert is_fresher_friendly("Graduate Engineer Trainee (GET)", None) is True
    assert is_fresher_friendly("Budget Analyst", None) is False
    assert is_fresher_friendly("Targeting Analyst", None) is False
    assert is_fresher_friendly("Software Engineer Intern", None) is True
    assert is_fresher_friendly("Senior Architect", 8.0) is False
    assert is_fresher_friendly("Backend Engineer", 0.0) is True


def test_scope_sql_fragment():
    assert geo.SCOPE_SQL == "j.city IS NOT NULL"
