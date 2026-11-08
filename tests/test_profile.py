"""Tests for profile parsing and ``extends`` resolution."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from ue_render_profiles_toolset.core.profile import (
    MAX_CVARS,
    MAX_EXTENDS_DEPTH,
    MAX_JSON_BYTES,
    MAX_NOTE_LENGTH,
    Profile,
    is_cvar_name,
    is_number,
    merge_cvars,
    profile_from_dict,
    profile_from_json,
    resolve_chain,
    resolve_profile,
)
from ue_render_profiles_toolset.errors import ProfileError, clip


def _profiles(*items: Profile) -> dict[str, Profile]:
    return {item.name: item for item in items}


def test_child_values_override_parent_values_key_by_key() -> None:
    profiles = _profiles(
        Profile("base", cvars={"r.Fog": 1, "r.ScreenPercentage": 100.0, "sg.ShadowQuality": 1}),
        Profile("balanced", extends="base", cvars={"sg.ShadowQuality": 2}),
        Profile("child", extends="balanced", cvars={"r.ScreenPercentage": 75.0}),
    )
    resolved = resolve_profile("child", profiles)
    assert dict(resolved.cvars) == {
        "r.Fog": 1,
        "r.ScreenPercentage": 75.0,
        "sg.ShadowQuality": 2,
    }
    assert [item.name for item in resolve_chain("child", profiles)] == ["child", "balanced", "base"]


def test_cycle_a_b_a_raises_extends_cycle_naming_the_cycle() -> None:
    profiles = _profiles(Profile("a", extends="b"), Profile("b", extends="a"))
    with pytest.raises(ProfileError) as info:
        resolve_profile("a", profiles)
    assert info.value.code == "extends_cycle"
    assert "a -> b -> a" in info.value.message


def test_self_cycle_is_detected() -> None:
    with pytest.raises(ProfileError) as info:
        resolve_profile("a", _profiles(Profile("a", extends="a")))
    assert info.value.code == "extends_cycle"
    assert "a -> a" in info.value.message


def test_unknown_profile_and_unknown_parent() -> None:
    with pytest.raises(ProfileError) as info:
        resolve_profile("missing", {})
    assert info.value.code == "unknown_profile"
    with pytest.raises(ProfileError) as parent:
        resolve_profile("child", _profiles(Profile("child", extends="ghost")))
    assert parent.value.code == "unknown_profile"


def test_extends_depth_limit() -> None:
    last = MAX_EXTENDS_DEPTH - 1
    ok = {
        f"p{i}": Profile(f"p{i}", extends=f"p{i + 1}" if i < last else None)
        for i in range(MAX_EXTENDS_DEPTH)
    }
    assert len(resolve_chain("p0", ok)) == MAX_EXTENDS_DEPTH
    too_deep = {
        f"p{i}": Profile(f"p{i}", extends=f"p{i + 1}") for i in range(MAX_EXTENDS_DEPTH + 4)
    }
    with pytest.raises(ProfileError) as info:
        resolve_chain("p0", too_deep)
    assert info.value.code == "invalid_profile"


def test_note_and_hardware_are_inherited_when_empty() -> None:
    profiles = _profiles(
        Profile("base", note="base note", target_hardware="gpu"),
        Profile("child", extends="base"),
    )
    resolved = resolve_profile("child", profiles)
    assert resolved.note == "base note"
    assert resolved.target_hardware == "gpu"
    assert resolved.extends == "base"


def test_profile_is_immutable() -> None:
    profile = Profile("a", cvars={"r.Fog": 1})
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.name = "b"  # type: ignore[misc]
    with pytest.raises(TypeError):
        profile.cvars["r.Fog"] = 2  # type: ignore[index]


def test_profile_from_dict_valid() -> None:
    profile = profile_from_dict(
        {
            "name": "p1",
            "extends": "base",
            "note": "n",
            "target_hardware": "h",
            "cvars": {"r.Fog": 1, "r.ScreenPercentage": 75.5},
        }
    )
    assert profile.name == "p1"
    assert profile.extends == "base"
    assert dict(profile.cvars) == {"r.Fog": 1, "r.ScreenPercentage": 75.5}
    assert profile_from_dict({"name": "minimal"}).cvars == {}


BAD_PROFILES: list[Any] = [
    [],
    {},
    {"name": "ok", "bogus": 1},
    {"name": "bad name"},
    {"name": "ok\n"},
    {"name": "ok", "extends": 5},
    {"name": "ok", "note": 5},
    {"name": "ok", "note": "x" * (MAX_NOTE_LENGTH + 1)},
    {"name": "ok", "cvars": []},
    {"name": "ok", "cvars": {"bad name": 1}},
    {"name": "ok", "cvars": {1: 2}},
    {"name": "ok", "cvars": {"r.Fog": True}},
    {"name": "ok", "cvars": {"r.Fog": "1"}},
    {"name": "ok", "cvars": {"r.Fog": float("nan")}},
    {"name": "ok", "cvars": {"r.Fog": 10**15}},
    {"name": "ok", "cvars": {f"r.Test{i}": 1 for i in range(MAX_CVARS + 1)}},
]


@pytest.mark.parametrize("data", BAD_PROFILES)
def test_profile_from_dict_rejects_bad_input(data: Any) -> None:
    with pytest.raises(ProfileError) as info:
        profile_from_dict(data)
    assert info.value.code == "invalid_profile"


def test_profile_from_json() -> None:
    assert profile_from_json('{"name": "a", "cvars": {"r.Fog": 0}}').cvars == {"r.Fog": 0}
    for text in ["{not json", "[" * 200000, "[]", "x" * (MAX_JSON_BYTES + 1)]:
        with pytest.raises(ProfileError) as info:
            profile_from_json(text)
        assert info.value.code == "invalid_profile"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, True),
        (1.5, True),
        (True, False),
        ("1", False),
        (None, False),
        (float("nan"), False),
        (float("inf"), False),
        (10**400, False),
    ],
)
def test_is_number(value: object, expected: bool) -> None:
    assert is_number(value) is expected


def test_is_cvar_name() -> None:
    assert is_cvar_name("r.Lumen.TraceMeshSDFs")
    assert not is_cvar_name("r.Fog 1")
    assert not is_cvar_name("r.Fog\n")
    assert not is_cvar_name(5)


def test_merge_cvars() -> None:
    assert merge_cvars() == {}
    assert merge_cvars({"a": 1, "b": 2}, {"b": 3}) == {"a": 1, "b": 3}


def test_error_messages_are_clipped() -> None:
    error = ProfileError("invalid_profile", "x" * 500)
    assert len(error.message) == 200
    assert error.code == "invalid_profile"
    assert str(error).startswith("invalid_profile: ")
    assert clip("abcdef", 5) == "ab..."
    assert clip("abc", 5) == "abc"
