"""Tests for plans, the snapshot store, diff and the ini export."""

from __future__ import annotations

from pathlib import Path

import pytest

from ue_render_profiles_toolset.core.catalog import load_catalog, load_profiles
from ue_render_profiles_toolset.core.diff import diff_cvars
from ue_render_profiles_toolset.core.ini import LEVEL_INDEX, render_scalability_ini
from ue_render_profiles_toolset.core.plan import (
    ApplyPlan,
    PlannedCommand,
    Snapshot,
    SnapshotStore,
    build_apply_plan,
    build_command,
    build_revert_plan,
    coerce_value,
    find_mismatches,
    format_value,
    values_close,
)
from ue_render_profiles_toolset.core.profile import Profile, resolve_profile
from ue_render_profiles_toolset.errors import ProfileError

CATALOG = load_catalog()
GOLDEN_RELATIVE = "tests/golden/DefaultScalability.ini"
GOLDEN = Path(__file__).parent / "fixtures" / "golden" / "DefaultScalability.ini"


def test_diff_between_resolved_profiles_lists_values_and_impact() -> None:
    profiles = load_profiles()
    left = resolve_profile("balanced", profiles)
    right = resolve_profile("trailer-max", profiles)
    entries = diff_cvars(left.cvars, right.cvars, CATALOG)
    assert [(e.cvar, e.left, e.right) for e in entries] == [
        ("r.Streaming.PoolSize", 1000, 3000),
        ("sg.GlobalIlluminationQuality", 2, 4),
        ("sg.ShadowQuality", 2, 4),
    ]
    assert entries[0].impact == "not documented"
    assert entries[2].impact == CATALOG.cvars["sg.ShadowQuality"].impact


def test_diff_handles_missing_sides_and_unknown_cvars() -> None:
    entries = diff_cvars(
        {"r.Fog": 1, "x.Unknown": 1}, {"r.Fog": 1.0, "r.Streaming.PoolSize": 5}, CATALOG
    )
    assert [(e.cvar, e.left, e.right, e.impact) for e in entries] == [
        ("r.Streaming.PoolSize", None, 5, "not documented"),
        ("x.Unknown", 1, None, "not documented"),
    ]


def test_format_and_coerce_values() -> None:
    int_spec = CATALOG.cvars["r.Fog"]
    float_spec = CATALOG.cvars["r.ScreenPercentage"]
    assert format_value(int_spec, 3) == "3"
    assert format_value(int_spec, 3.0) == "3"
    assert format_value(float_spec, 75) == "75.0"
    assert coerce_value(float_spec, 0.5) == 0.5
    for bad in [3.5, True, "1", float("nan"), float("inf")]:
        with pytest.raises(ProfileError):
            coerce_value(int_spec, bad)


def test_build_command_only_names_whitelisted_cvars() -> None:
    assert build_command(CATALOG, "r.Fog", 0) == "r.Fog 0"
    with pytest.raises(ProfileError):
        build_command(CATALOG, "r.Not.Listed", 1)
    with pytest.raises(ProfileError):
        build_command(CATALOG, "r.Fog 1; quit", 1)


def test_apply_plan_orders_groups_first_and_skips_restart_cvars() -> None:
    profile = Profile(
        "p",
        cvars={"r.Fog": 1, "sg.ShadowQuality": 2, "r.Shadow.Virtual.Enable": 1},
    )
    plan = build_apply_plan(profile, CATALOG, {"r.Fog": 0})
    assert [c.text for c in plan.commands] == ["sg.ShadowQuality 2", "r.Fog 1"]
    assert plan.commands[1].before == 0
    assert plan.commands[0].before is None
    assert plan.skipped_restart == ("r.Shadow.Virtual.Enable",)
    with pytest.raises(ProfileError):
        build_apply_plan(Profile("p", cvars={"r.Nope": 1}), CATALOG, {})


def test_revert_plan_restores_only_changed_touched_cvars() -> None:
    snapshot = Snapshot(
        1,
        "p",
        {"r.Fog": 1, "sg.ShadowQuality": 2, "r.ScreenPercentage": 100.0},
        ("r.Fog", "sg.ShadowQuality", "r.ScreenPercentage", "r.Streaming.PoolSize"),
    )
    current = {"r.Fog": 0, "sg.ShadowQuality": 2}
    plan = build_revert_plan(snapshot, CATALOG, current)
    assert [c.text for c in plan.commands] == ["r.Fog 1", "r.ScreenPercentage 100.0"]
    assert plan.profile == "revert:p"


def test_find_mismatches_uses_a_tolerance() -> None:
    plan = ApplyPlan(
        "p",
        (
            PlannedCommand("r.ScreenPercentage", None, 0.1, "r.ScreenPercentage 0.1"),
            PlannedCommand("r.Fog", None, 1, "r.Fog 1"),
            PlannedCommand("r.Streaming.PoolSize", None, 5, "r.Streaming.PoolSize 5"),
        ),
        (),
    )
    readback = {"r.ScreenPercentage": 0.10000000149, "r.Fog": 0}
    found = find_mismatches(plan, readback)
    assert [(m.cvar, m.requested, m.actual) for m in found] == [
        ("r.Fog", 1, 0),
        ("r.Streaming.PoolSize", 5, None),
    ]
    assert values_close(100, 100.0)
    assert not values_close(100, 75)


def test_snapshot_store_is_bounded_and_ordered() -> None:
    store = SnapshotStore(max_entries=2)
    for index in range(3):
        store.push(f"p{index}", {"r.Fog": index}, ("r.Fog",))
    assert len(store) == 2
    assert store.peek().snapshot_id == 3
    assert store.pop().snapshot_id == 3
    assert store.pop().snapshot_id == 2
    with pytest.raises(ProfileError) as info:
        store.pop()
    assert info.value.code == "nothing_to_revert"
    with pytest.raises(ProfileError):
        store.peek()
    store.push("p", {}, ())
    store.clear()
    assert len(store) == 0
    with pytest.raises(ValueError):
        SnapshotStore(max_entries=0)


def test_ini_matches_golden_for_low_medium_high() -> None:
    profiles = load_profiles()
    levels = {
        "Low": resolve_profile("lumen-lite-6gb", profiles),
        "Medium": resolve_profile("balanced", profiles),
        "High": resolve_profile("trailer-max", profiles),
    }
    export = render_scalability_ini(levels, CATALOG)
    assert export.text == GOLDEN.read_bytes().decode("utf-8")
    assert Path(GOLDEN_RELATIVE).name == GOLDEN.name
    assert export.skipped_cvars == (
        "r.AntiAliasingMethod",
        "r.Fog",
        "r.ScreenPercentage",
        "sg.GlobalIlluminationQuality",
        "sg.ShadowQuality",
    )
    assert LEVEL_INDEX["Low"] == 0


def test_ini_rejects_bad_levels_and_unknown_cvars() -> None:
    with pytest.raises(ProfileError):
        render_scalability_ini({}, CATALOG)
    with pytest.raises(ProfileError):
        render_scalability_ini({"Ultra": Profile("p")}, CATALOG)
    with pytest.raises(ProfileError):
        render_scalability_ini({"Low": Profile("p", cvars={"r.Nope": 1})}, CATALOG)
