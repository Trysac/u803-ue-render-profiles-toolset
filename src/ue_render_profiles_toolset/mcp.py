"""MCP-facing functions: flat, JSON-friendly parameters in, one JSON string out.

The Unreal plugin's toolset class (``plugin/RenderProfilesToolset/Content/Python``) only forwards
to these functions with the real ``unreal`` module, so everything an agent sees is tested here with
a fake. Inputs are primitives (the level map of ``export_scalability_ini`` travels as a JSON
string) and every result is a JSON object whose first key is ``summary``. Errors never raise to
the agent: they come back as ``{"summary": "error: ...", "error": {"code": ..., "message": ...}}``.

Snapshots and captured profiles live in ``session`` (module level, mirrored to a JSON file under
``<Project>/Saved/``), so ``apply_profile`` and ``revert_last`` work across separate MCP calls.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any

from . import adapter
from .core.profile import Profile, load_json, profile_from_dict
from .errors import CODE_INVALID_PROFILE, ProfileError
from .session import Session, get_session, save_session

MAX_JSON_CHARS = 1_000_000
SNAPSHOT_NOTE = "snapshot of live editor values"


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _plain(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def to_json(result: Any) -> str:
    """Serialize a result with ``summary`` first."""
    data = _plain(result)
    if isinstance(data, dict) and "summary" in data:
        data = {"summary": data["summary"], **{k: v for k, v in data.items() if k != "summary"}}
    return json.dumps(data, ensure_ascii=False)


def _error(code: str, message: str) -> str:
    return json.dumps(
        {"summary": f"error: {message[:200]}", "error": {"code": code, "message": message[:200]}}
    )


def _run(call: Callable[[], Any]) -> str:
    try:
        return to_json(call())
    except ProfileError as exc:
        return _error(exc.code, exc.message)
    except OSError as exc:
        return _error("io_error", f"{type(exc).__name__}: {exc}")
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return _error("unreal_error", f"{type(exc).__name__}: {exc}")


def _registry(ue: Any, state: Session) -> dict[str, Profile]:
    return adapter.load_registry(ue, state.captured)


def _with_state(result: Any, state: Session, persisted: bool | None = None) -> dict[str, Any]:
    data: dict[str, Any] = _plain(result)
    if persisted is not None:
        data["persisted"] = persisted
        data["state_file"] = None if state.path is None else str(state.path)
    if state.warning:
        data["state_warning"] = state.warning
    return data


def list_profiles(ue: Any) -> str:
    """List built-in, project (Config/RenderProfiles) and captured snapshot profiles."""
    return _run(lambda: adapter.list_profiles(ue, captured=get_session(ue).captured))


def describe_profile(ue: Any, name: str) -> str:
    """Resolve one profile: extends chain, merged CVars and validation issues."""
    return _run(lambda: adapter.describe_profile(ue, name, _registry(ue, get_session(ue))))


def snapshot_current(ue: Any, name: str = "") -> str:
    """Read every whitelisted CVar; with ``name``, keep the values as a session profile."""

    def call() -> Any:
        state = get_session(ue)
        result = adapter.snapshot_current(ue)
        if not name:
            return _with_state(result, state)
        if name == adapter.CURRENT or name in adapter.load_registry(ue):
            message = f"{name[:64]} is reserved or names a built-in or project profile"
            raise ProfileError(CODE_INVALID_PROFILE, message)
        profile = profile_from_dict({"name": name, "note": SNAPSHOT_NOTE, "cvars": result.values})
        state.captured[name] = profile
        persisted = save_session(state)
        data = _with_state(result, state, persisted)
        data["summary"] = f"{result.summary}; saved as profile {name}"
        data["saved_as"] = name
        return data

    return _run(call)


def diff_profiles(ue: Any, left: str, right: str = adapter.CURRENT) -> str:
    """Diff two profiles; either side may be ``current`` (live editor values)."""
    return _run(lambda: adapter.diff_profiles(ue, left, right, _registry(ue, get_session(ue))))


def apply_profile(ue: Any, name: str, dry_run: bool = True) -> str:
    """Apply a profile with whitelisted console commands (dry run by default)."""

    def call() -> Any:
        state = get_session(ue)
        result = adapter.apply_profile(ue, name, dry_run, _registry(ue, state), state.store)
        persisted = None if dry_run else save_session(state)
        return _with_state(result, state, persisted)

    return _run(call)


def revert_last(ue: Any, dry_run: bool = True) -> str:
    """Restore the values recorded before the last real apply (dry run by default)."""

    def call() -> Any:
        state = get_session(ue)
        result = adapter.revert_last(ue, dry_run, state.store)
        persisted = None if dry_run else save_session(state)
        return _with_state(result, state, persisted)

    return _run(call)


def _levels(levels_json: str) -> dict[str, str]:
    if not isinstance(levels_json, str) or len(levels_json) > MAX_JSON_CHARS:
        raise ProfileError(CODE_INVALID_PROFILE, "levels_json must be a JSON string under 1 MB")
    data = load_json(levels_json, "levels_json")
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        message = 'levels_json must be an object like {"Low": "lumen-lite-6gb"}'
        raise ProfileError(CODE_INVALID_PROFILE, message)
    return data


def export_scalability_ini(
    ue: Any, levels_json: str, write: bool = False, dry_run: bool = True
) -> str:
    """Render DefaultScalability.ini; writes Config/ only with write=True and dry_run=False."""

    def call() -> Any:
        levels = _levels(levels_json)
        registry = _registry(ue, get_session(ue))
        return adapter.export_scalability_ini(
            ue, levels, write=write, dry_run=dry_run, profiles=registry
        )

    return _run(call)
