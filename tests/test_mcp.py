"""The MCP layer: JSON in, JSON out, errors as data, session state across calls."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fakes.unreal import make_fake

from ue_render_profiles_toolset import mcp
from ue_render_profiles_toolset.core.catalog import load_catalog
from ue_render_profiles_toolset.session import get_session, reset_session

LEVELS = json.dumps({"Low": "lumen-lite-6gb", "Medium": "balanced", "High": "trailer-max"})
GOLDEN = Path(__file__).parent / "fixtures" / "golden" / "DefaultScalability.ini"


@pytest.fixture(autouse=True)
def fresh_session() -> Iterator[None]:
    reset_session()
    yield
    reset_session()


def _load(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    assert next(iter(data)) == "summary"
    return data


def _project(tmp_path: Path) -> tuple[Path, Path]:
    config = tmp_path / "Config"
    saved = tmp_path / "Saved"
    config.mkdir()
    saved.mkdir()
    return config, saved


def _write_profile(config: Path, data: dict[str, Any], file_name: str | None = None) -> None:
    folder = config / "RenderProfiles"
    folder.mkdir(exist_ok=True)
    (folder / (file_name or f"{data['name']}.json")).write_text(json.dumps(data), "utf-8")


def test_dry_run_apply_executes_nothing() -> None:
    ue = make_fake()
    data = _load(mcp.apply_profile(ue, "lumen-lite-6gb"))
    assert data["dry_run"] is True
    assert data["commands_executed"] == 0
    assert data["commands"][0] == "sg.GlobalIlluminationQuality 1"
    assert "persisted" not in data
    assert ue.console.executed == []


def test_apply_and_revert_across_calls_restore_every_cvar(tmp_path: Path) -> None:
    config, saved = _project(tmp_path)
    ue = make_fake(config_dir=str(config), saved_dir=str(saved))
    before = _load(mcp.snapshot_current(ue))["values"]
    applied = _load(mcp.apply_profile(ue, "lumen-lite-6gb", dry_run=False))
    assert applied["commands_executed"] == 9
    assert applied["persisted"] is True
    state = Path(applied["state_file"])
    assert state.is_file() and state.parent.parent == saved
    planned = _load(mcp.revert_last(ue))
    assert planned["dry_run"] is True and planned["commands_executed"] == 0
    reverted = _load(mcp.revert_last(ue, dry_run=False))
    assert reverted["commands_executed"] > 0 and reverted["mismatched"] == []
    assert _load(mcp.snapshot_current(ue))["values"] == before
    assert _load(mcp.revert_last(ue, dry_run=False))["error"]["code"] == "nothing_to_revert"


def test_revert_survives_a_python_reload(tmp_path: Path) -> None:
    config, saved = _project(tmp_path)
    ue = make_fake(config_dir=str(config), saved_dir=str(saved))
    before = _load(mcp.snapshot_current(ue))["values"]
    snapshot_id = _load(mcp.apply_profile(ue, "trailer-max", dry_run=False))["snapshot_id"]
    reset_session()  # what a module reload does to the in-memory store
    reverted = _load(mcp.revert_last(ue, dry_run=False))
    assert reverted["snapshot_id"] == snapshot_id
    assert _load(mcp.snapshot_current(ue))["values"] == before
    reset_session()
    again = _load(mcp.apply_profile(ue, "balanced", dry_run=False))
    assert again["snapshot_id"] == snapshot_id + 1


def test_without_saved_dir_state_stays_in_memory() -> None:
    ue = make_fake()
    applied = _load(mcp.apply_profile(ue, "balanced", dry_run=False))
    assert applied["persisted"] is False and applied["state_file"] is None
    assert _load(mcp.revert_last(ue, dry_run=False))["persisted"] is False


def test_unreadable_session_file_is_reported_and_replaced(tmp_path: Path) -> None:
    config, saved = _project(tmp_path)
    state = saved / "RenderProfilesToolset" / "session.json"
    state.parent.mkdir()
    state.write_text("{not json", "utf-8")
    ue = make_fake(config_dir=str(config), saved_dir=str(saved))
    data = _load(mcp.revert_last(ue))
    assert data["error"]["code"] == "nothing_to_revert"
    applied = _load(mcp.apply_profile(ue, "balanced", dry_run=False))
    assert "unreadable session file" in applied["state_warning"]
    assert json.loads(state.read_text("utf-8"))["version"] == 1


def test_failed_save_is_reported_not_raised(tmp_path: Path) -> None:
    blocker = tmp_path / "Saved"
    blocker.write_text("a file where a folder is expected", "utf-8")
    ue = make_fake(saved_dir=str(blocker))
    applied = _load(mcp.apply_profile(ue, "balanced", dry_run=False))
    assert applied["persisted"] is False
    assert "not saved" in applied["state_warning"]
    assert applied["commands_executed"] > 0


def test_missing_cvars_are_reported_and_not_sent() -> None:
    ue = make_fake(absent=["r.Fog"])
    snap = _load(mcp.snapshot_current(ue))
    assert snap["missing"] == ["r.Fog"] and "1 missing" in snap["summary"]
    dry = _load(mcp.apply_profile(ue, "balanced"))
    assert dry["missing_cvars"] == ["r.Fog"] and "missing" in dry["summary"]
    real = _load(mcp.apply_profile(ue, "balanced", dry_run=False))
    assert real["missing_cvars"] == ["r.Fog"]
    assert not any(cmd.startswith("r.Fog ") for cmd in ue.console.executed)
    assert _load(mcp.diff_profiles(ue, "balanced"))["missing"] == ["r.Fog"]


def test_restart_cvars_are_flagged_and_never_sent() -> None:
    ue = make_fake()
    described = _load(mcp.describe_profile(ue, "balanced"))
    assert {"restart_required"} == {i["code"] for i in described["issues"]}
    applied = _load(mcp.apply_profile(ue, "balanced", dry_run=False))
    assert applied["skipped_restart"] == ["r.Shadow.Virtual.Enable"]
    whitelist = load_catalog().whitelist
    assert all(cmd.split(" ")[0] in whitelist for cmd in ue.console.executed)
    assert not any(cmd.startswith("r.Shadow.Virtual.Enable") for cmd in ue.console.executed)


def test_project_profiles_override_builtins_and_extend_them(tmp_path: Path) -> None:
    config, saved = _project(tmp_path)
    _write_profile(config, {"name": "balanced", "cvars": {"r.ScreenPercentage": 90}})
    _write_profile(config, {"name": "studio-pc", "extends": "trailer-max", "cvars": {"r.Fog": 0}})
    ue = make_fake(config_dir=str(config), saved_dir=str(saved))
    listing = _load(mcp.list_profiles(ue))
    sources = {p["name"]: p["source"] for p in listing["profiles"]}
    assert sources == {
        "balanced": "project",
        "lumen-lite-6gb": "builtin",
        "studio-pc": "project",
        "trailer-max": "builtin",
    }
    described = _load(mcp.describe_profile(ue, "studio-pc"))
    assert described["chain"] == ["studio-pc", "trailer-max", "balanced"]
    assert described["cvars"]["r.ScreenPercentage"] == 90
    assert described["cvars"]["r.Fog"] == 0
    applied = _load(mcp.apply_profile(ue, "balanced", dry_run=False))
    assert applied["commands"] == ["r.ScreenPercentage 90.0"]


def test_project_profile_with_unknown_cvar_never_emits_commands(tmp_path: Path) -> None:
    config, _ = _project(tmp_path)
    _write_profile(config, {"name": "evil", "cvars": {"r.Not.Whitelisted": 1}})
    ue = make_fake(config_dir=str(config))
    data = _load(mcp.apply_profile(ue, "evil", dry_run=False))
    assert data["error"]["code"] == "invalid_profile"
    assert ue.console.executed == []
    issues = _load(mcp.describe_profile(ue, "evil"))["issues"]
    assert [i["code"] for i in issues] == ["unknown_cvar"]


@pytest.mark.parametrize(
    ("file_name", "body", "needle"),
    [
        ("bad.json", "{oops", "RenderProfiles/bad.json"),
        ("other.json", json.dumps({"name": "named-else"}), "file name does not match"),
        ("current.json", json.dumps({"name": "current"}), "reserved"),
    ],
)
def test_bad_project_files_are_reported(
    tmp_path: Path, file_name: str, body: str, needle: str
) -> None:
    config, _ = _project(tmp_path)
    (config / "RenderProfiles").mkdir()
    (config / "RenderProfiles" / file_name).write_text(body, "utf-8")
    data = _load(mcp.list_profiles(make_fake(config_dir=str(config))))
    assert data["error"]["code"] == "invalid_profile"
    assert needle in data["error"]["message"]


def test_too_many_or_too_large_project_files_are_rejected(tmp_path: Path) -> None:
    config, _ = _project(tmp_path)
    folder = config / "RenderProfiles"
    folder.mkdir()
    (folder / "big.json").write_text(" " * 1_048_577, "utf-8")
    assert "too large" in _load(mcp.list_profiles(make_fake(config_dir=str(config))))["summary"]
    (folder / "big.json").unlink()
    for index in range(65):
        (folder / f"p{index}.json").write_text(json.dumps({"name": f"p{index}"}), "utf-8")
    data = _load(mcp.list_profiles(make_fake(config_dir=str(config))))
    assert data["error"]["code"] == "invalid_profile"


def test_named_snapshot_becomes_a_session_profile(tmp_path: Path) -> None:
    config, saved = _project(tmp_path)
    ue = make_fake(config_dir=str(config), saved_dir=str(saved))
    data = _load(mcp.snapshot_current(ue, "before-trailer"))
    assert data["saved_as"] == "before-trailer" and data["persisted"] is True
    assert "saved as profile" in data["summary"]
    mcp.apply_profile(ue, "trailer-max", dry_run=False)
    diff = _load(mcp.diff_profiles(ue, "before-trailer", "current"))
    assert {e["cvar"] for e in diff["entries"]} >= {"sg.ShadowQuality"}
    reset_session()
    listing = _load(mcp.list_profiles(ue))
    assert {"name": "before-trailer", "source": "snapshot"}.items() <= next(
        p for p in listing["profiles"] if p["name"] == "before-trailer"
    ).items()
    back = _load(mcp.apply_profile(ue, "before-trailer", dry_run=False))
    assert back["mismatched"] == []
    assert _load(mcp.diff_profiles(ue, "before-trailer"))["entries"] == []
    assert len(get_session(ue).captured) == 1


@pytest.mark.parametrize("name", ["balanced", "current", "bad name!"])
def test_named_snapshot_rejects_reserved_or_invalid_names(name: str) -> None:
    data = _load(mcp.snapshot_current(make_fake(), name))
    assert data["error"]["code"] == "invalid_profile"


def test_diff_between_profiles_and_against_current() -> None:
    ue = make_fake()
    diff = _load(mcp.diff_profiles(ue, "balanced", "trailer-max"))
    assert [e["cvar"] for e in diff["entries"]] == [
        "r.Streaming.PoolSize",
        "sg.GlobalIlluminationQuality",
        "sg.ShadowQuality",
    ]
    live = _load(mcp.diff_profiles(ue, "current", "current"))
    assert live["entries"] == [] and live["missing"] == []
    against = _load(mcp.diff_profiles(ue, "current", "balanced"))
    assert all(e["impact"] for e in against["entries"])
    assert _load(mcp.diff_profiles(ue, "nope"))["error"]["code"] == "unknown_profile"


def test_export_returns_text_and_writes_only_when_asked(tmp_path: Path) -> None:
    config, _ = _project(tmp_path)
    ue = make_fake(config_dir=str(config))
    text = _load(mcp.export_scalability_ini(ue, LEVELS))
    assert text["text"] == GOLDEN.read_bytes().decode("utf-8")
    assert text["written"] is False
    dry = _load(mcp.export_scalability_ini(ue, LEVELS, write=True))
    assert dry["written"] is False and list(config.iterdir()) == []
    real = _load(mcp.export_scalability_ini(ue, LEVELS, write=True, dry_run=False))
    assert real["written"] is True
    assert (config / "DefaultScalability.ini").read_bytes() == GOLDEN.read_bytes()


@pytest.mark.parametrize(
    "levels", ["{bad", "[1]", json.dumps({"Low": 3}), json.dumps({"Ultra": "balanced"})]
)
def test_export_rejects_bad_levels(levels: str) -> None:
    data = _load(mcp.export_scalability_ini(make_fake(), levels))
    assert data["error"]["code"] == "invalid_profile"
    assert data["summary"].startswith("error:")


def test_export_rejects_huge_levels_json() -> None:
    data = _load(mcp.export_scalability_ini(make_fake(), "x" * (mcp.MAX_JSON_CHARS + 1)))
    assert data["error"]["code"] == "invalid_profile"


def test_io_errors_come_back_as_data(tmp_path: Path) -> None:
    config, _ = _project(tmp_path)
    (config / "DefaultScalability.ini").mkdir()
    ue = make_fake(config_dir=str(config))
    data = _load(mcp.export_scalability_ini(ue, LEVELS, write=True, dry_run=False))
    assert data["error"]["code"] == "io_error"


def test_unexpected_unreal_failure_is_reported() -> None:
    ue = make_fake()
    del ue.SystemLibrary
    data = _load(mcp.snapshot_current(ue))
    assert data["error"]["code"] == "unreal_error"


def test_to_json_handles_plain_values() -> None:
    out = json.loads(mcp.to_json({"a": (1, 2), "summary": "s", "p": object.__new__(object)}))
    assert next(iter(out)) == "summary" and out["a"] == [1, 2] and isinstance(out["p"], str)
    assert json.loads(mcp.to_json([1, None]))[1] is None
