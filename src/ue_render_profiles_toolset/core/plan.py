"""Apply and revert plans, command whitelist enforcement and the snapshot store."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Collection, Mapping
from dataclasses import dataclass

from ue_render_profiles_toolset.core.catalog import Catalog, CVarSpec
from ue_render_profiles_toolset.core.profile import (
    Number,
    Profile,
    is_cvar_name,
    is_number,
)
from ue_render_profiles_toolset.errors import (
    CODE_INVALID_PROFILE,
    CODE_NOTHING_TO_REVERT,
    ProfileError,
    clip,
)

DEFAULT_MAX_SNAPSHOTS = 16
STORE_FORMAT_VERSION = 1


@dataclass(frozen=True)
class PlannedCommand:
    """One console command with the value it replaces (``before``) when known."""

    cvar: str
    before: Number | None
    value: Number
    text: str


@dataclass(frozen=True)
class ApplyPlan:
    """Ordered commands plus the CVars skipped because they need a restart or are missing.

    ``skipped_missing`` names CVars of the profile that this engine version does not expose.
    """

    profile: str
    commands: tuple[PlannedCommand, ...]
    skipped_restart: tuple[str, ...]
    skipped_missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class Mismatch:
    """A CVar whose read-back value differs from the requested one."""

    cvar: str
    requested: Number
    actual: Number | None


@dataclass(frozen=True)
class Snapshot:
    """Values read before an apply; ``touched`` names the CVars the apply wrote."""

    snapshot_id: int
    profile: str
    values: Mapping[str, Number]
    touched: tuple[str, ...]


def require_spec(catalog: Catalog, name: str) -> CVarSpec:
    """Return the catalog spec of ``name`` or raise: only whitelisted CVars are allowed."""
    spec = catalog.get(name)
    if spec is None:
        raise ProfileError(CODE_INVALID_PROFILE, f"cvar not in whitelist: {clip(name, 60)}")
    return spec


def coerce_value(spec: CVarSpec, value: object) -> Number:
    """Return ``value`` as the catalog type, rejecting non-numeric or non-integral input."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not is_number(value):
        raise ProfileError(
            CODE_INVALID_PROFILE,
            f"value for {clip(spec.name, 60)} must be a finite number",
        )
    if spec.type == "int":
        if isinstance(value, float):
            if not value.is_integer():
                raise ProfileError(
                    CODE_INVALID_PROFILE,
                    f"value for {clip(spec.name, 60)} must be an integer",
                )
            return int(value)
        return value
    return float(value)


def format_value(spec: CVarSpec, value: object) -> str:
    """Format a value for a console command or an ini file."""
    coerced = coerce_value(spec, value)
    return str(coerced) if spec.type == "int" else repr(coerced)


def build_command(catalog: Catalog, cvar: str, value: object) -> str:
    """Return ``'<cvar> <number>'``; the only command shape this library emits."""
    spec = require_spec(catalog, cvar)
    return f"{spec.name} {format_value(spec, value)}"


def _order(name: str) -> tuple[int, str]:
    # sg.* groups re-apply their CVars, so they must run before individual CVars.
    return (0 if name.startswith("sg.") else 1, name)


def build_apply_plan(
    profile: Profile,
    catalog: Catalog,
    current: Mapping[str, Number],
    available: Collection[str] | None = None,
) -> ApplyPlan:
    """Plan the commands that apply a resolved profile.

    When ``available`` is given, CVars of the profile not in it (absent from this engine
    version) get no command and are listed in ``skipped_missing`` instead of failing silently.
    """
    commands: list[PlannedCommand] = []
    skipped: list[str] = []
    missing: list[str] = []
    for name in sorted(profile.cvars, key=_order):
        spec = require_spec(catalog, name)
        if spec.requires_restart:
            skipped.append(name)
            continue
        if available is not None and name not in available:
            missing.append(name)
            continue
        value = coerce_value(spec, profile.cvars[name])
        text = build_command(catalog, name, value)
        commands.append(PlannedCommand(name, current.get(name), value, text))
    return ApplyPlan(profile.name, tuple(commands), tuple(skipped), tuple(missing))


def build_revert_plan(
    snapshot: Snapshot,
    catalog: Catalog,
    current: Mapping[str, Number],
) -> ApplyPlan:
    """Plan the commands that restore every snapshot value that differs from the current one.

    All snapshot values are considered, not only the touched CVars: writing an ``sg.*`` group
    re-applies other CVars in the engine, so those must be restored too (``sg.*`` first).
    """
    commands: list[PlannedCommand] = []
    for name in sorted(snapshot.values, key=_order):
        wanted = snapshot.values[name]
        if current.get(name) == wanted:
            continue
        text = build_command(catalog, name, wanted)
        commands.append(PlannedCommand(name, current.get(name), wanted, text))
    return ApplyPlan(f"revert:{snapshot.profile}", tuple(commands), ())


def values_close(left: Number, right: Number) -> bool:
    """Tolerant comparison used for read-back checks (engine floats are single precision)."""
    return math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-9)


def find_mismatches(plan: ApplyPlan, readback: Mapping[str, Number]) -> tuple[Mismatch, ...]:
    """Return the planned CVars whose read-back value differs from the requested one."""
    found: list[Mismatch] = []
    for item in plan.commands:
        actual = readback.get(item.cvar)
        if actual is None or not values_close(actual, item.value):
            found.append(Mismatch(item.cvar, item.value, actual))
    return tuple(found)


class SnapshotStore:
    """Bounded in-memory stack of snapshots; the oldest entries are evicted first."""

    def __init__(self, max_entries: int = DEFAULT_MAX_SNAPSHOTS) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._items: deque[Snapshot] = deque(maxlen=max_entries)
        self._next_id = 1

    def push(
        self,
        profile: str,
        values: Mapping[str, Number],
        touched: tuple[str, ...],
    ) -> Snapshot:
        """Store a snapshot and return it."""
        snapshot = Snapshot(self._next_id, profile, dict(values), touched)
        self._next_id += 1
        self._items.append(snapshot)
        return snapshot

    def peek(self) -> Snapshot:
        """Return the newest snapshot without removing it."""
        if not self._items:
            raise ProfileError(CODE_NOTHING_TO_REVERT, "no snapshot to revert to")
        return self._items[-1]

    def pop(self) -> Snapshot:
        """Remove and return the newest snapshot."""
        snapshot = self.peek()
        self._items.pop()
        return snapshot

    def clear(self) -> None:
        """Drop every snapshot."""
        self._items.clear()

    def to_dict(self) -> dict[str, object]:
        """Return the store as plain JSON-compatible data (oldest snapshot first)."""
        return {
            "version": STORE_FORMAT_VERSION,
            "next_id": self._next_id,
            "snapshots": [
                {
                    "snapshot_id": item.snapshot_id,
                    "profile": item.profile,
                    "values": dict(item.values),
                    "touched": list(item.touched),
                }
                for item in self._items
            ],
        }

    @classmethod
    def from_dict(cls, data: object, max_entries: int = DEFAULT_MAX_SNAPSHOTS) -> SnapshotStore:
        """Rebuild a store saved by ``to_dict``; raise ``invalid_profile`` on malformed data."""
        if not isinstance(data, dict) or data.get("version") != STORE_FORMAT_VERSION:
            raise _state_error("expected an object with version 1")
        next_id = data.get("next_id")
        raw_items = data.get("snapshots")
        if isinstance(next_id, bool) or not isinstance(next_id, int) or next_id < 1:
            raise _state_error("next_id must be a positive integer")
        if not isinstance(raw_items, list):
            raise _state_error("snapshots must be a list")
        store = cls(max_entries)
        for raw in raw_items:
            store._items.append(_snapshot_from_dict(raw))
        store._next_id = max([next_id, *(item.snapshot_id + 1 for item in store._items)])
        return store

    def __len__(self) -> int:
        return len(self._items)


def _state_error(message: str) -> ProfileError:
    return ProfileError(CODE_INVALID_PROFILE, f"snapshot state: {message}")


def _snapshot_from_dict(raw: object) -> Snapshot:
    if not isinstance(raw, dict):
        raise _state_error("each snapshot must be an object")
    snapshot_id = raw.get("snapshot_id")
    profile = raw.get("profile")
    values = raw.get("values")
    touched = raw.get("touched")
    if isinstance(snapshot_id, bool) or not isinstance(snapshot_id, int) or snapshot_id < 1:
        raise _state_error("snapshot_id must be a positive integer")
    if not isinstance(profile, str) or not isinstance(values, dict):
        raise _state_error("profile must be a string and values an object")
    if not isinstance(touched, list) or not all(is_cvar_name(item) for item in touched):
        raise _state_error("touched must be a list of cvar names")
    for name, value in values.items():
        if not is_cvar_name(name) or not is_number(value):
            raise _state_error(f"invalid value for {clip(str(name), 60)}")
    return Snapshot(snapshot_id, clip(profile, 64), dict(values), tuple(touched))
