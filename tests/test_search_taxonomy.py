from fastapi.datastructures import QueryParams

from app.services import taxonomy
from app.services.search import JobFilters, expand_role, looks_fresher_query, parse_filters


def test_expand_role_react():
    extras = expand_role("react developer jobs")
    assert "frontend developer" in extras and "mern developer" in extras


def test_expand_role_python_sql_bi():
    extras = expand_role("python + sql + power bi analyst")
    assert isinstance(extras, list)


def test_looks_fresher_query():
    assert looks_fresher_query("fresher python jobs")
    assert not looks_fresher_query("senior architect")


def test_parse_filters_defaults_and_bounds():
    f = parse_filters(QueryParams({"page": "3", "per_page": "999"}))
    assert f.page == 3 and f.per_page == 50
    f2 = parse_filters(QueryParams({}))
    assert f2.sort == "freshness" and f2.page == 1


def test_parse_filters_fresher_flag():
    f = parse_filters(QueryParams({"fresher": "1"}))
    assert f.fresher is True


def test_skill_alias_resolution():
    assert taxonomy.resolve_skill("ReactJS") == taxonomy.resolve_skill("React")
    assert taxonomy.resolve_skill("React.js") == taxonomy.resolve_skill("React")
    assert taxonomy.resolve_skill("react js") == taxonomy.resolve_skill("React")
    assert taxonomy.resolve_skill("k8s") == taxonomy.resolve_skill("Kubernetes")
    assert taxonomy.resolve_skill("NonexistentSkillXYZ") is None


def test_normalize_list_dedupes():
    out = taxonomy.normalize_list(["React", "ReactJS", "React.js", "Python"])
    names = [n for _, n in out]
    assert names.count("React") == 1 and "Python" in names


def test_job_filters_dataclass_defaults():
    f = JobFilters()
    assert f.sort == "freshness" and f.per_page == 20 and f.extra_terms == []
