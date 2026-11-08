"""Result dataclasses returned by the adapter functions; each has a one-line ``summary``."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from ue_render_profiles_toolset.core.diff import DiffEntry
from ue_render_profiles_toolset.core.plan import Mismatch
from ue_render_profiles_toolset.core.profile import Number
from ue_render_profiles_toolset.core.schema import ValidationIssue


@dataclass(frozen=True)
class ProfileInfo:
    """Short description of a profile in a listing."""

    name: str
    extends: str | None
    note: str
    target_hardware: str
    cvar_count: int


@dataclass(frozen=True)
class ListProfilesResult:
    """Result of ``list_profiles``."""

    summary: str
    profiles: tuple[ProfileInfo, ...]


@dataclass(frozen=True)
class DescribeProfileResult:
    """Result of ``describe_profile``: the resolved CVars and validation issues."""

    summary: str
    name: str
    chain: tuple[str, ...]
    note: str
    target_hardware: str
    cvars: dict[str, Number]
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True)
class SnapshotResult:
    """Result of ``snapshot_current``: the live value of every whitelisted CVar."""

    summary: str
    values: dict[str, Number]


@dataclass(frozen=True)
class DiffResult:
    """Result of ``diff_profiles``."""

    summary: str
    left: str
    right: str
    entries: tuple[DiffEntry, ...]


@dataclass(frozen=True)
class ApplyResult:
    """Result of ``apply_profile``: ``commands`` is the plan, ``commands_executed`` the count."""

    summary: str
    profile: str
    dry_run: bool
    commands: tuple[str, ...]
    commands_executed: int
    skipped_restart: tuple[str, ...]
    mismatched: tuple[str, ...]
    mismatch_details: tuple[Mismatch, ...]
    snapshot_id: int | None


@dataclass(frozen=True)
class RevertResult:
    """Result of ``revert_last``."""

    summary: str
    snapshot_id: int
    profile: str
    dry_run: bool
    commands: tuple[str, ...]
    commands_executed: int
    mismatched: tuple[str, ...]
    mismatch_details: tuple[Mismatch, ...]


@dataclass(frozen=True)
class ExportResult:
    """Result of ``export_scalability_ini``."""

    summary: str
    text: str
    levels: dict[str, str]
    skipped_cvars: tuple[str, ...]
    dry_run: bool
    written: bool
    path: str | None


def to_dict(result: object) -> dict[str, Any]:
    """Convert a result dataclass into plain data (for MCP tool responses)."""
    if not is_dataclass(result) or isinstance(result, type):
        raise TypeError("to_dict expects a result dataclass instance")
    return asdict(result)
