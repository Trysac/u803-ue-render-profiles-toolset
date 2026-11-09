"""Snapshot store serialization and the session file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ue_render_profiles_toolset import Profile, ProfileError
from ue_render_profiles_toolset.core.plan import SnapshotStore
from ue_render_profiles_toolset.session import (
    Session,
    load_session,
    save_session,
    session_from_dict,
    session_to_dict,
)


def test_store_round_trip_keeps_order_and_next_id() -> None:
    store = SnapshotStore()
    store.push("a", {"r.Fog": 1}, ("r.Fog",))
    store.push("b", {"r.ScreenPercentage": 75.0}, ("r.ScreenPercentage",))
    store.pop()
    copy = SnapshotStore.from_dict(json.loads(json.dumps(store.to_dict())))
    assert len(copy) == 1 and copy.peek().profile == "a"
    assert copy.push("c", {}, ()).snapshot_id == 3


def test_next_id_never_reuses_a_stored_id() -> None:
    data = {
        "version": 1,
        "next_id": 1,
        "snapshots": [{"snapshot_id": 7, "profile": "p", "values": {}, "touched": []}],
    }
    assert SnapshotStore.from_dict(data).push("q", {}, ()).snapshot_id == 8


GOOD = {"snapshot_id": 1, "profile": "p", "values": {"r.Fog": 1}, "touched": ["r.Fog"]}


@pytest.mark.parametrize(
    "data",
    [
        None,
        {"version": 2, "next_id": 1, "snapshots": []},
        {"version": 1, "next_id": True, "snapshots": []},
        {"version": 1, "next_id": 1, "snapshots": {}},
        {"version": 1, "next_id": 2, "snapshots": ["x"]},
        {"version": 1, "next_id": 2, "snapshots": [{**GOOD, "snapshot_id": 0}]},
        {"version": 1, "next_id": 2, "snapshots": [{**GOOD, "values": []}]},
        {"version": 1, "next_id": 2, "snapshots": [{**GOOD, "touched": ["bad name"]}]},
        {"version": 1, "next_id": 2, "snapshots": [{**GOOD, "values": {"r.Fog": "1"}}]},
    ],
)
def test_malformed_store_is_rejected(data: Any) -> None:
    with pytest.raises(ProfileError) as info:
        SnapshotStore.from_dict(data)
    assert info.value.code == "invalid_profile"


def test_session_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "Saved" / "RenderProfilesToolset" / "session.json"
    session = Session(path=path)
    session.captured["mine"] = Profile("mine", note="n", cvars={"r.Fog": 0})
    session.store.push("balanced", {"r.Fog": 1}, ("r.Fog",))
    assert save_session(session) is True
    loaded = load_session(path)
    assert loaded.warning is None
    assert dict(loaded.captured["mine"].cvars) == {"r.Fog": 0}
    assert loaded.store.peek().profile == "balanced"
    assert session_to_dict(loaded) == session_to_dict(session)


def test_session_without_path_is_not_saved() -> None:
    assert save_session(Session()) is False
    assert load_session(None).path is None


@pytest.mark.parametrize("data", [[], {"version": 1, "captured": {}}])
def test_malformed_session_is_rejected(data: Any) -> None:
    with pytest.raises(ProfileError):
        session_from_dict(data)
