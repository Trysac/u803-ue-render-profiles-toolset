"""Thin adapter between the pure core and the Unreal Python API.

Every public function takes the ``unreal`` module (or a fake) as its first argument ``ue``.
CVars are read with ``ue.SystemLibrary.get_console_variable_*_value`` and written with
``ue.SystemLibrary.execute_console_command``; only whitelisted ``<cvar> <number>`` commands are
sent. These calls are exercised against a fake console in the tests, not inside Unreal.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ue_render_profiles_toolset.core.catalog import (
    Catalog,
    CVarSpec,
    load_catalog,
    load_profiles,
)
from ue_render_profiles_toolset.core.diff import diff_cvars
from ue_render_profiles_toolset.core.ini import render_scalability_ini
from ue_render_profiles_toolset.core.plan import (
    SnapshotStore,
    build_apply_plan,
    build_revert_plan,
    find_mismatches,
)
from ue_render_profiles_toolset.core.profile import (
    Number,
    Profile,
    resolve_chain,
    resolve_profile,
)
from ue_render_profiles_toolset.core.schema import ensure_valid, validate_profile
from ue_render_profiles_toolset.errors import CODE_INVALID_PROFILE, ProfileError, clip
from ue_render_profiles_toolset.results import (
    ApplyResult,
    DescribeProfileResult,
    DiffResult,
    ExportResult,
    ListProfilesResult,
    ProfileInfo,
    RevertResult,
    SnapshotResult,
)

CONFIG_DIR_NAME = "Config"
SCALABILITY_FILE_NAME = "DefaultScalability.ini"

_DEFAULT_STORE = SnapshotStore()


def default_store() -> SnapshotStore:
    """Return the process-wide snapshot store used when no ``store`` is passed."""
    return _DEFAULT_STORE


def _registry(profiles: Mapping[str, Profile] | None) -> Mapping[str, Profile]:
    return load_profiles() if profiles is None else profiles


def _world(ue: Any) -> Any:
    return ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()


def _read_value(ue: Any, spec: CVarSpec) -> Number:
    library = ue.SystemLibrary
    if spec.type == "int":
        return int(library.get_console_variable_int_value(spec.name))
    return float(library.get_console_variable_float_value(spec.name))


def _read_names(ue: Any, catalog: Catalog, names: Iterable[str]) -> dict[str, Number]:
    values: dict[str, Number] = {}
    for name in names:
        spec = catalog.get(name)
        if spec is not None:
            values[name] = _read_value(ue, spec)
    return values


def _execute(ue: Any, catalog: Catalog, command: str) -> None:
    parts = command.split(" ")
    if len(parts) != 2 or parts[0] not in catalog:
        message = f"command is not whitelisted: {clip(parts[0], 60)}"
        raise ProfileError(CODE_INVALID_PROFILE, message)
    ue.SystemLibrary.execute_console_command(_world(ue), command)


def list_profiles(ue: Any, profiles: Mapping[str, Profile] | None = None) -> ListProfilesResult:
    """List the available profiles."""
    registry = _registry(profiles)
    infos = tuple(
        ProfileInfo(
            name=name,
            extends=registry[name].extends,
            note=registry[name].note,
            target_hardware=registry[name].target_hardware,
            cvar_count=len(registry[name].cvars),
        )
        for name in sorted(registry)
    )
    return ListProfilesResult(summary=f"{len(infos)} profiles available", profiles=infos)


def describe_profile(
    ue: Any,
    name: str,
    profiles: Mapping[str, Profile] | None = None,
) -> DescribeProfileResult:
    """Describe a profile: its resolved CVars, extends chain and validation issues."""
    registry = _registry(profiles)
    chain = tuple(item.name for item in resolve_chain(name, registry))
    resolved = resolve_profile(name, registry)
    issues = validate_profile(resolved, load_catalog())
    return DescribeProfileResult(
        summary=f"{clip(name, 64)} sets {len(resolved.cvars)} cvars, {len(issues)} issues",
        name=name,
        chain=chain,
        note=resolved.note,
        target_hardware=resolved.target_hardware,
        cvars={key: resolved.cvars[key] for key in sorted(resolved.cvars)},
        issues=issues,
    )


def snapshot_current(ue: Any) -> SnapshotResult:
    """Read the current value of every whitelisted CVar (read-only; nothing is stored)."""
    catalog = load_catalog()
    values = _read_names(ue, catalog, sorted(catalog.cvars))
    return SnapshotResult(summary=f"Read {len(values)} cvars", values=values)


def diff_profiles(
    ue: Any,
    left: str,
    right: str,
    profiles: Mapping[str, Profile] | None = None,
) -> DiffResult:
    """Diff two resolved profiles: every CVar whose value differs, with the impact note."""
    registry = _registry(profiles)
    first = resolve_profile(left, registry)
    second = resolve_profile(right, registry)
    entries = diff_cvars(first.cvars, second.cvars, load_catalog())
    summary = f"{len(entries)} cvars differ between {clip(left, 64)} and {clip(right, 64)}"
    return DiffResult(summary=summary, left=left, right=right, entries=entries)


def apply_profile(
    ue: Any,
    name: str,
    dry_run: bool = True,
    profiles: Mapping[str, Profile] | None = None,
    store: SnapshotStore | None = None,
) -> ApplyResult:
    """Apply a profile. With ``dry_run=True`` (default) no console command is executed.

    Unless dry-running, a snapshot is stored first, commands run, and every written CVar is
    read back; CVars whose value differs from the request are listed under ``mismatched``.
    """
    catalog = load_catalog()
    resolved = resolve_profile(name, _registry(profiles))
    ensure_valid(resolved, catalog)
    current = _read_names(ue, catalog, sorted(catalog.cvars))
    plan = build_apply_plan(resolved, catalog, current)
    commands = tuple(item.text for item in plan.commands)
    label = clip(name, 64)
    if dry_run:
        return ApplyResult(
            summary=f"Dry run of {label}: {len(commands)} commands planned, 0 executed",
            profile=name,
            dry_run=True,
            commands=commands,
            commands_executed=0,
            skipped_restart=plan.skipped_restart,
            mismatched=(),
            mismatch_details=(),
            snapshot_id=None,
        )
    target = _DEFAULT_STORE if store is None else store
    touched = tuple(item.cvar for item in plan.commands)
    snapshot = target.push(name, current, touched)
    for item in plan.commands:
        _execute(ue, catalog, item.text)
    readback = _read_names(ue, catalog, touched)
    details = find_mismatches(plan, readback)
    return ApplyResult(
        summary=f"Applied {label}: {len(commands)} commands executed, {len(details)} mismatched",
        profile=name,
        dry_run=False,
        commands=commands,
        commands_executed=len(commands),
        skipped_restart=plan.skipped_restart,
        mismatched=tuple(item.cvar for item in details),
        mismatch_details=details,
        snapshot_id=snapshot.snapshot_id,
    )


def revert_last(
    ue: Any,
    dry_run: bool = False,
    store: SnapshotStore | None = None,
) -> RevertResult:
    """Restore the CVars written by the last apply to their snapshot values.

    Raises:
        ProfileError: ``nothing_to_revert`` when no snapshot is stored.
    """
    catalog = load_catalog()
    target = _DEFAULT_STORE if store is None else store
    snapshot = target.peek()
    current = _read_names(ue, catalog, sorted(snapshot.values))
    plan = build_revert_plan(snapshot, catalog, current)
    commands = tuple(item.text for item in plan.commands)
    if dry_run:
        return RevertResult(
            summary=f"Dry run of revert: {len(commands)} commands planned, 0 executed",
            snapshot_id=snapshot.snapshot_id,
            profile=snapshot.profile,
            dry_run=True,
            commands=commands,
            commands_executed=0,
            mismatched=(),
            mismatch_details=(),
        )
    for item in plan.commands:
        _execute(ue, catalog, item.text)
    readback = _read_names(ue, catalog, [item.cvar for item in plan.commands])
    details = find_mismatches(plan, readback)
    target.pop()
    return RevertResult(
        summary=f"Reverted snapshot {snapshot.snapshot_id}: {len(commands)} commands executed",
        snapshot_id=snapshot.snapshot_id,
        profile=snapshot.profile,
        dry_run=False,
        commands=commands,
        commands_executed=len(commands),
        mismatched=tuple(item.cvar for item in details),
        mismatch_details=details,
    )


def _safe_config_path(config_dir: Path) -> Path:
    resolved = config_dir.resolve()
    if resolved.name != CONFIG_DIR_NAME or not resolved.is_dir():
        message = "files may only be written inside the project's Config/ folder"
        raise ProfileError(CODE_INVALID_PROFILE, message)
    return resolved / SCALABILITY_FILE_NAME


def export_scalability_ini(
    ue: Any,
    levels: Mapping[str, str],
    config_dir: str | Path | None = None,
    write: bool = False,
    dry_run: bool = True,
    profiles: Mapping[str, Profile] | None = None,
) -> ExportResult:
    """Render ``DefaultScalability.ini`` for ``{level name: profile name}``.

    A file is written only with ``write=True`` and ``dry_run=False``, and only as
    ``DefaultScalability.ini`` inside a folder named ``Config`` (default: the project's Config).
    """
    catalog = load_catalog()
    registry = _registry(profiles)
    resolved: dict[str, Profile] = {}
    for level, profile_name in levels.items():
        profile = resolve_profile(profile_name, registry)
        ensure_valid(profile, catalog)
        resolved[level] = profile
    export = render_scalability_ini(resolved, catalog)
    written = False
    path: str | None = None
    if write and not dry_run:
        base = Path(str(ue.Paths.project_config_dir())) if config_dir is None else Path(config_dir)
        target = _safe_config_path(base)
        target.write_text(export.text, encoding="utf-8", newline="\n")
        written = True
        path = str(target)
    if written:
        summary = f"Wrote {SCALABILITY_FILE_NAME} with {len(levels)} levels"
    elif write:
        summary = f"Dry run: {SCALABILITY_FILE_NAME} rendered, 0 files written"
    else:
        summary = f"Rendered {SCALABILITY_FILE_NAME} with {len(levels)} levels, 0 files written"
    return ExportResult(
        summary=summary,
        text=export.text,
        levels=dict(levels),
        skipped_cvars=export.skipped_cvars,
        dry_run=dry_run,
        written=written,
        path=path,
    )
