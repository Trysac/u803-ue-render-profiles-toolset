"""Tests for the catalog, the packaged profiles and validation."""

from __future__ import annotations

from typing import Any

import pytest

from ue_render_profiles_toolset.core.catalog import (
    DOCS_PREFIX,
    MAX_CATALOG_ENTRIES,
    MAX_PROFILES,
    NOT_DOCUMENTED,
    load_catalog,
    load_profiles,
    parse_catalog,
    profiles_from_texts,
)
from ue_render_profiles_toolset.core.profile import MAX_CVARS, Profile, resolve_profile
from ue_render_profiles_toolset.core.schema import (
    ensure_valid,
    has_errors,
    validate_profile,
)
from ue_render_profiles_toolset.errors import ProfileError

CATALOG = load_catalog()
DOCS = "https://dev.epicgames.com/documentation/en-us/unreal-engine/"


def _entry(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": "r.Test.Value",
        "type": "int",
        "range": "not documented",
        "description": "Test value.",
        "impact": "not documented",
        "source": DOCS + "scalability-reference-for-unreal-engine",
        "warnings": [],
        "requires_restart": False,
        "scalability_group": None,
    }
    entry.update(overrides)
    return entry


def test_catalog_contains_required_cvars() -> None:
    for name in [
        "sg.GlobalIlluminationQuality",
        "sg.ShadowQuality",
        "r.Shadow.Virtual.Enable",
        "r.AntiAliasingMethod",
        "r.ScreenPercentage",
        "r.Fog",
        "r.Streaming.PoolSize",
    ]:
        assert name in CATALOG
    assert sum(1 for name in CATALOG.cvars if name.startswith("r.Lumen.")) >= 3
    assert CATALOG.whitelist == frozenset(CATALOG.cvars)
    assert CATALOG.get("r.Nope") is None


def test_catalog_entries_are_documented_and_honest() -> None:
    for spec in CATALOG.cvars.values():
        assert spec.source.startswith(DOCS_PREFIX)
        assert spec.description
        assert spec.impact
    assert CATALOG.cvars["sg.ShadowQuality"].range_text == "0..4"
    assert CATALOG.cvars["r.Fog"].range_text == NOT_DOCUMENTED
    assert CATALOG.cvars["r.Shadow.Virtual.Enable"].requires_restart is True


def test_packaged_profiles_load_and_validate() -> None:
    profiles = load_profiles()
    assert sorted(profiles) == ["balanced", "lumen-lite-6gb", "trailer-max"]
    for name, profile in profiles.items():
        assert "example, validate on your hardware" in profile.note
        resolved = resolve_profile(name, profiles)
        assert not has_errors(validate_profile(resolved, CATALOG))
        ensure_valid(resolved, CATALOG)
    codes = [i.code for i in validate_profile(profiles["balanced"], CATALOG)]
    assert codes == ["restart_required"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "string"},
        {"range": "1..2"},
        {"range": {"min": 3, "max": 1}},
        {"range": {"min": "a", "max": 1}},
        {"range": {"min": 1}},
        {"description": ""},
        {"source": "http://example.com/docs"},
        {"warnings": "x"},
        {"warnings": [1]},
        {"requires_restart": "no"},
        {"scalability_group": 5},
        {"name": "bad name"},
    ],
)
def test_parse_catalog_rejects_bad_entries(overrides: dict[str, Any]) -> None:
    with pytest.raises(ProfileError) as info:
        parse_catalog({"version": 1, "cvars": [_entry(**overrides)]})
    assert info.value.code == "invalid_profile"


def test_parse_catalog_rejects_bad_documents() -> None:
    extra = _entry()
    extra["bogus"] = 1
    bad_documents: list[Any] = [
        [],
        {"version": 2, "cvars": []},
        {"version": 1, "cvars": {}},
        {"version": 1, "cvars": [5]},
        {"version": 1, "cvars": [extra]},
        {"version": 1, "cvars": [_entry(), _entry()]},
        {"version": 1, "cvars": [_entry()] * (MAX_CATALOG_ENTRIES + 1)},
    ]
    for document in bad_documents:
        with pytest.raises(ProfileError):
            parse_catalog(document)


def test_parse_catalog_accepts_a_range() -> None:
    catalog = parse_catalog(
        {"version": 1, "cvars": [_entry(range={"min": 0, "max": 4}, scalability_group="G")]}
    )
    spec = catalog.cvars["r.Test.Value"]
    assert (spec.minimum, spec.maximum, spec.scalability_group) == (0.0, 4.0, "G")


def test_profiles_from_texts() -> None:
    texts = {"a.json": '{"name": "a"}', "b.json": '{"name": "b", "extends": "a"}'}
    assert sorted(profiles_from_texts(texts)) == ["a", "b"]
    with pytest.raises(ProfileError):
        profiles_from_texts({"other.json": '{"name": "a"}'})
    many = {f"p{i}.json": f'{{"name": "p{i}"}}' for i in range(MAX_PROFILES + 1)}
    with pytest.raises(ProfileError):
        profiles_from_texts(many)


def test_unknown_cvar_is_reported_not_silent() -> None:
    profile = Profile("x", cvars={"r.Nope.Missing": 1})
    issues = validate_profile(profile, CATALOG)
    assert [(i.code, i.cvar, i.severity) for i in issues] == [
        ("unknown_cvar", "r.Nope.Missing", "error")
    ]
    with pytest.raises(ProfileError) as info:
        ensure_valid(profile, CATALOG)
    assert info.value.code == "invalid_profile"
    assert "unknown_cvar" in info.value.message


def test_validation_reports_type_and_range_problems() -> None:
    profile = Profile(
        "x",
        cvars={
            "sg.ShadowQuality": 9,
            "r.Fog": 1.5,
            "r.ScreenPercentage": "fast",  # type: ignore[dict-item]
            "r.AntiAliasingMethod": 2,
        },
    )
    found = {(i.cvar, i.code) for i in validate_profile(profile, CATALOG)}
    assert found == {
        ("sg.ShadowQuality", "out_of_range"),
        ("r.Fog", "invalid_type"),
        ("r.ScreenPercentage", "invalid_type"),
    }


def test_validation_limits_cvar_count() -> None:
    profile = Profile("x", cvars={f"r.Test{i}": 1 for i in range(MAX_CVARS + 1)})
    issues = validate_profile(profile, CATALOG)
    assert [i.code for i in issues] == ["too_many_cvars"]
