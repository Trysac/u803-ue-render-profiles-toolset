"""Hypothesis properties (derandomized) for the core and the adapter."""

from __future__ import annotations

from typing import Any

from fakes.unreal import make_fake
from hypothesis import given, settings
from hypothesis import strategies as st

from ue_render_profiles_toolset import apply_profile, revert_last, snapshot_current
from ue_render_profiles_toolset.core.catalog import CVarSpec, load_catalog
from ue_render_profiles_toolset.core.plan import SnapshotStore
from ue_render_profiles_toolset.core.profile import Profile, merge_cvars

CATALOG = load_catalog()
NAMES = sorted(CATALOG.cvars)
SETTINGS = settings(derandomize=True, max_examples=60, deadline=None)
LEVELS = st.dictionaries(st.sampled_from(NAMES), st.integers(-100, 100), max_size=6)


def _values(spec: CVarSpec) -> st.SearchStrategy[Any]:
    low = -1000 if spec.minimum is None else spec.minimum
    high = 1000 if spec.maximum is None else spec.maximum
    if spec.type == "int":
        return st.integers(min_value=int(low), max_value=int(high))
    return st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False)


@st.composite
def generated_profiles(draw: st.DrawFn) -> Profile:
    names = draw(st.lists(st.sampled_from(NAMES), unique=True))
    cvars = {name: draw(_values(CATALOG.cvars[name])) for name in names}
    return Profile(name="generated", cvars=cvars)


@st.composite
def console_tables(draw: st.DrawFn) -> dict[str, Any]:
    return {name: draw(_values(spec)) for name, spec in CATALOG.cvars.items()}


@SETTINGS
@given(first=LEVELS, second=LEVELS, third=LEVELS)
def test_merge_is_associative_by_levels(
    first: dict[str, int],
    second: dict[str, int],
    third: dict[str, int],
) -> None:
    left = merge_cvars(merge_cvars(first, second), third)
    right = merge_cvars(first, merge_cvars(second, third))
    assert left == right == merge_cvars(first, second, third)


@SETTINGS
@given(profile=generated_profiles(), table=console_tables())
def test_apply_then_revert_restores_the_snapshot(profile: Profile, table: dict[str, Any]) -> None:
    ue = make_fake(values=table)
    store = SnapshotStore()
    registry = {"generated": profile}
    before = snapshot_current(ue).values
    result = apply_profile(ue, "generated", dry_run=False, profiles=registry, store=store)
    assert result.mismatched == ()
    revert_last(ue, store=store)
    assert snapshot_current(ue).values == before
    assert ue.console.ignored == []


@SETTINGS
@given(profile=generated_profiles())
def test_no_command_names_anything_outside_the_whitelist(profile: Profile) -> None:
    ue = make_fake()
    registry = {"generated": profile}
    dry = apply_profile(ue, "generated", dry_run=True, profiles=registry, store=SnapshotStore())
    assert ue.console.executed == []
    live = apply_profile(ue, "generated", dry_run=False, profiles=registry, store=SnapshotStore())
    assert dry.commands == live.commands
    assert len(ue.console.executed) == len(live.commands)
    for command in ue.console.executed:
        name, value = command.split(" ")
        assert name in CATALOG.whitelist
        float(value)
