"""Diff of two sets of CVar values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ue_render_profiles_toolset.core.catalog import NOT_DOCUMENTED, Catalog
from ue_render_profiles_toolset.core.profile import Number


@dataclass(frozen=True)
class DiffEntry:
    """A CVar whose value differs; a side is None when it does not set the CVar."""

    cvar: str
    left: Number | None
    right: Number | None
    impact: str


def diff_cvars(
    left: Mapping[str, Number],
    right: Mapping[str, Number],
    catalog: Catalog,
) -> tuple[DiffEntry, ...]:
    """List every CVar whose value differs, sorted by name, with the catalog impact note."""
    entries: list[DiffEntry] = []
    for name in sorted(set(left) | set(right)):
        before = left.get(name)
        after = right.get(name)
        if before == after:
            continue
        spec = catalog.get(name)
        impact = NOT_DOCUMENTED if spec is None else spec.impact
        entries.append(DiffEntry(name, before, after, impact))
    return tuple(entries)
