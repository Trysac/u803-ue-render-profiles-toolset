"""Adapter tests on the fake console (nothing here ran inside Unreal)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.unreal import make_fake

from ue_render_profiles_toolset import (
    Profile,
    ProfileError,
    apply_profile,
    describe_profile,
    diff_profiles,
    export_scalability_ini,
    list_profiles,
    revert_last,
    snapshot_current,
)
from ue_render_profiles_toolset.adapter import _execute, default_store
from ue_render_profiles_toolset.core.catalog import load_catalog
from ue_render_profiles_toolset.core.plan import SnapshotStore

GOLDEN = Path(__file__).parent / "fixtures" / "golden" / "DefaultScalability.ini"
LEVELS = {"Low": "lumen-lite-6gb", "Medium": "balanced", "High": "trailer-max"}


def test_list_and_describe_profiles() -> None:
    ue = make_fake()
    listing = list_profiles(ue)
    assert [p.name for p in listing.profiles] == ["balanced", "lumen-lite-6gb", "trailer-max"]
    assert listing.summary == "3 profiles available"
    described = describe_profile(ue, "lumen-lite-6gb")
    assert described.chain == ("lumen-lite-6gb", "balanced")
    assert described.cvars["r.ScreenPercentage"] == 75
    assert described.cvars["r.Fog"] == 1
    assert [i.code for i in described.issues] == ["restart_required"]
    with pytest.raises(ProfileError) as info:
        describe_profile(ue, "nope")
    assert info.value.code == "unknown_profile"


def test_snapshot_current_reads_every_whitelisted_cvar() -> None:
    ue = make_fake(values={"r.ScreenPercentage": 88.5})
    result = snapshot_current(ue)
    assert sorted(result.values) == sorted(load_catalog().cvars)
    assert result.values["r.ScreenPercentage"] == 88.5
    assert ue.console.executed == []


def test_diff_profiles_balanced_vs_trailer_max() -> None:
    result = diff_profiles(make_fake(), "balanced", "trailer-max")
    assert [(e.cvar, e.left, e.right) for e in result.entries] == [
        ("r.Streaming.PoolSize", 1000, 3000),
        ("sg.GlobalIlluminationQuality", 2, 4),
        ("sg.ShadowQuality", 2, 4),
    ]
    assert result.summary == "3 cvars differ between balanced and trailer-max"


def test_dry_run_executes_no_command_and_lists_each_command() -> None:
    ue = make_fake()
    result = apply_profile(ue, "lumen-lite-6gb", dry_run=True, store=SnapshotStore())
    assert ue.console.executed == []
    assert result.commands_executed == 0
    assert result.dry_run is True
    assert result.commands == (
        "sg.GlobalIlluminationQuality 1",
        "sg.ShadowQuality 1",
        "r.AntiAliasingMethod 4",
        "r.Fog 1",
        "r.Lumen.DiffuseIndirect.Allow 1",
        "r.Lumen.Reflections.Allow 0",
        "r.Lumen.TraceMeshSDFs 0",
        "r.ScreenPercentage 75.0",
        "r.Streaming.PoolSize 500",
    )
    assert result.skipped_restart == ("r.Shadow.Virtual.Enable",)
    assert result.snapshot_id is None


def test_apply_then_revert_restores_every_snapshot_value_exactly() -> None:
    ue = make_fake()
    store = SnapshotStore()
    before = snapshot_current(ue).values
    applied = apply_profile(ue, "lumen-lite-6gb", dry_run=False, store=store)
    assert applied.commands_executed == 9
    assert applied.mismatched == ()
    assert snapshot_current(ue).values["r.ScreenPercentage"] == 75.0
    reverted = revert_last(ue, store=store)
    assert reverted.commands_executed > 0
    assert reverted.mismatched == ()
    assert snapshot_current(ue).values == before
    assert ue.console.ignored == []
    assert len(store) == 0


def test_revert_restores_cvars_changed_by_sg_group_side_effects() -> None:
    side = "r.Lumen.ScreenProbeGather.DownsampleFactor"
    ue = make_fake(
        values={side: 32},
        group_effects={"sg.GlobalIlluminationQuality": {side: 8}},
    )
    store = SnapshotStore()
    before = snapshot_current(ue).values
    apply_profile(ue, "lumen-lite-6gb", dry_run=False, store=store)
    assert ue.console.values[side] == 8
    reverted = revert_last(ue, store=store)
    assert reverted.mismatched == ()
    assert snapshot_current(ue).values == before


def test_readback_mismatch_is_reported() -> None:
    ue = make_fake(forced={"r.ScreenPercentage": 75})
    result = apply_profile(ue, "balanced", dry_run=False, store=SnapshotStore())
    assert "r.ScreenPercentage" in result.mismatched
    assert result.mismatched == ("r.ScreenPercentage",)
    detail = result.mismatch_details[0]
    assert (detail.requested, detail.actual) == (100, 75)
    assert "1 mismatched" in result.summary


def test_revert_dry_run_and_nothing_to_revert() -> None:
    ue = make_fake()
    store = SnapshotStore()
    with pytest.raises(ProfileError) as info:
        revert_last(ue, store=store)
    assert info.value.code == "nothing_to_revert"
    apply_profile(ue, "trailer-max", dry_run=False, store=store)
    dry = revert_last(ue, dry_run=True, store=store)
    assert dry.commands_executed == 0
    assert dry.dry_run is True
    assert len(store) == 1
    assert len(ue.console.executed) == 9


def test_default_store_is_used_when_none_is_passed() -> None:
    default_store().clear()
    ue = make_fake()
    applied = apply_profile(ue, "balanced", dry_run=False)
    assert applied.snapshot_id is not None
    assert len(default_store()) == 1
    revert_last(ue)
    assert len(default_store()) == 0


def test_apply_rejects_invalid_profiles_without_executing() -> None:
    ue = make_fake()
    bad = {"bad": Profile("bad", cvars={"r.Nope.Missing": 1})}
    with pytest.raises(ProfileError) as info:
        apply_profile(ue, "bad", dry_run=False, profiles=bad, store=SnapshotStore())
    assert info.value.code == "invalid_profile"
    assert ue.console.executed == []
    described = describe_profile(ue, "bad", profiles=bad)
    assert [i.code for i in described.issues] == ["unknown_cvar"]


def test_execute_refuses_non_whitelisted_commands() -> None:
    ue = make_fake()
    catalog = load_catalog()
    for command in ["quit", "r.Fog", "r.Fog 1 2", "stat fps 1"]:
        with pytest.raises(ProfileError):
            _execute(ue, catalog, command)
    assert ue.console.executed == []


def test_export_matches_golden_and_writes_nothing_by_default(tmp_path: Path) -> None:
    ue = make_fake()
    result = export_scalability_ini(ue, LEVELS)
    assert result.text == GOLDEN.read_bytes().decode("utf-8")
    assert result.written is False
    assert result.path is None
    assert list(tmp_path.iterdir()) == []


def test_export_write_with_dry_run_writes_zero_files(tmp_path: Path) -> None:
    config = tmp_path / "Config"
    config.mkdir()
    result = export_scalability_ini(
        make_fake(),
        LEVELS,
        config_dir=config,
        write=True,
        dry_run=True,
    )
    assert result.written is False
    assert list(config.iterdir()) == []
    assert "0 files written" in result.summary


def test_export_writes_golden_file_when_allowed(tmp_path: Path) -> None:
    config = tmp_path / "Config"
    config.mkdir()
    result = export_scalability_ini(
        make_fake(),
        LEVELS,
        config_dir=str(config),
        write=True,
        dry_run=False,
    )
    target = config / "DefaultScalability.ini"
    assert result.written is True
    assert result.path == str(target.resolve())
    assert target.read_bytes().decode("utf-8") == GOLDEN.read_bytes().decode("utf-8")


def test_export_uses_project_config_dir_from_unreal(tmp_path: Path) -> None:
    config = tmp_path / "Config"
    config.mkdir()
    ue = make_fake(config_dir=str(config))
    result = export_scalability_ini(ue, {"Medium": "balanced"}, write=True, dry_run=False)
    assert result.written is True
    assert (config / "DefaultScalability.ini").exists()


def test_export_refuses_folders_other_than_config(tmp_path: Path) -> None:
    other = tmp_path / "Elsewhere"
    other.mkdir()
    with pytest.raises(ProfileError):
        export_scalability_ini(make_fake(), LEVELS, config_dir=other, write=True, dry_run=False)
    with pytest.raises(ProfileError):
        export_scalability_ini(
            make_fake(),
            LEVELS,
            config_dir=tmp_path / "Config",
            write=True,
            dry_run=False,
        )
    assert list(other.iterdir()) == []


def test_export_rejects_unknown_levels_and_profiles() -> None:
    ue = make_fake()
    with pytest.raises(ProfileError):
        export_scalability_ini(ue, {"Ultra": "balanced"})
    with pytest.raises(ProfileError) as info:
        export_scalability_ini(ue, {"Low": "missing"})
    assert info.value.code == "unknown_profile"
