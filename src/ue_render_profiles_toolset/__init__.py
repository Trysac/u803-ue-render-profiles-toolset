"""Versioned Unreal Engine render profiles: pure core and Unreal MCP toolset adapter.

The pure core never imports ``unreal``; the adapter functions take the ``unreal`` module (or a
fake) as their first argument. ``mcp`` is the agent-facing layer used by the Unreal plugin.
"""

from __future__ import annotations

from ue_render_profiles_toolset.adapter import (
    apply_profile,
    describe_profile,
    diff_profiles,
    export_scalability_ini,
    list_profiles,
    load_project_profiles,
    load_registry,
    revert_last,
    snapshot_current,
)
from ue_render_profiles_toolset.core.catalog import load_catalog, load_profiles
from ue_render_profiles_toolset.core.profile import Profile, resolve_profile
from ue_render_profiles_toolset.core.schema import validate_profile
from ue_render_profiles_toolset.errors import ProfileError
from ue_render_profiles_toolset.results import (
    ApplyResult,
    DescribeProfileResult,
    DiffResult,
    ExportResult,
    ListProfilesResult,
    RevertResult,
    SnapshotResult,
)

__all__ = [
    "ApplyResult",
    "DescribeProfileResult",
    "DiffResult",
    "ExportResult",
    "ListProfilesResult",
    "Profile",
    "ProfileError",
    "RevertResult",
    "SnapshotResult",
    "__version__",
    "apply_profile",
    "describe_profile",
    "diff_profiles",
    "export_scalability_ini",
    "list_profiles",
    "load_catalog",
    "load_profiles",
    "load_project_profiles",
    "load_registry",
    "resolve_profile",
    "revert_last",
    "snapshot_current",
    "validate_profile",
]

__version__ = "0.2.0"
