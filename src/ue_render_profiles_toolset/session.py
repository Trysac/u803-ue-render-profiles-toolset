"""Editor-session state shared by separate MCP calls: the snapshot stack and captured profiles.

Each MCP tool call is a separate Python call inside the same editor process, so the state lives at
module level. It is also mirrored to ``<Project>/Saved/RenderProfilesToolset/session.json`` after
every change so that ``revert_last`` still works after a Python reload. A missing or unreadable file
starts an empty session; an unreadable one is reported through ``Session.warning`` (and replaced on
the next save). Console values reset when the editor restarts, while the file persists: a revert
after a restart only re-sends the values that differ from the recorded snapshot.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ue_render_profiles_toolset.core.plan import SnapshotStore
from ue_render_profiles_toolset.core.profile import Profile, load_json, profile_from_dict
from ue_render_profiles_toolset.errors import CODE_INVALID_PROFILE, ProfileError, clip

STATE_DIR_NAME = "RenderProfilesToolset"
STATE_FILE_NAME = "session.json"
STATE_VERSION = 1


@dataclass
class Session:
    """Mutable session state; ``path`` is None when the project Saved folder is unknown."""

    store: SnapshotStore = field(default_factory=SnapshotStore)
    captured: dict[str, Profile] = field(default_factory=dict)
    path: Path | None = None
    warning: str | None = None


class _Holder:
    current: Session | None = None


def state_path(ue: Any) -> Path | None:
    """Return ``<Project>/Saved/RenderProfilesToolset/session.json`` or None."""
    try:
        saved = Path(str(ue.Paths.project_saved_dir()))
    except RuntimeError:
        return None
    return saved / STATE_DIR_NAME / STATE_FILE_NAME


def _profile_to_dict(profile: Profile) -> dict[str, object]:
    return {
        "name": profile.name,
        "note": profile.note,
        "target_hardware": profile.target_hardware,
        "cvars": dict(profile.cvars),
    }


def session_to_dict(session: Session) -> dict[str, object]:
    """Return the session as JSON-compatible data."""
    return {
        "version": STATE_VERSION,
        "store": session.store.to_dict(),
        "captured": [_profile_to_dict(session.captured[name]) for name in sorted(session.captured)],
    }


def session_from_dict(data: object, path: Path | None = None) -> Session:
    """Rebuild a session saved by ``session_to_dict``; raise ``ProfileError`` when malformed."""
    if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
        raise ProfileError(CODE_INVALID_PROFILE, "session state: expected an object with version 1")
    raw_captured = data.get("captured")
    if not isinstance(raw_captured, list):
        raise ProfileError(CODE_INVALID_PROFILE, "session state: captured must be a list")
    captured = {item.name: item for item in (profile_from_dict(raw) for raw in raw_captured)}
    return Session(SnapshotStore.from_dict(data.get("store")), captured, path)


def load_session(path: Path | None) -> Session:
    """Load the session file at ``path``; start empty when it is absent or unreadable."""
    if path is None or not path.is_file():
        return Session(path=path)
    try:
        data = load_json(path.read_text(encoding="utf-8"), "session state")
        return session_from_dict(data, path)
    except (OSError, UnicodeDecodeError, ProfileError) as exc:
        message = clip(f"ignored unreadable session file {path.name}: {exc}")
        return Session(path=path, warning=message)


def get_session(ue: Any) -> Session:
    """Return the module-level session, loading it from the Saved folder on first use."""
    if _Holder.current is None:
        _Holder.current = load_session(state_path(ue))
    return _Holder.current


def reset_session() -> None:
    """Forget the in-memory session; the next ``get_session`` reloads it from disk."""
    _Holder.current = None


def save_session(session: Session) -> bool:
    """Write the session file atomically; return False (and set ``warning``) when it fails."""
    if session.path is None:
        return False
    try:
        session.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = session.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(session_to_dict(session), indent=2),
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, session.path)
    except OSError as exc:
        session.warning = clip(f"session file not saved: {exc}")
        return False
    return True
