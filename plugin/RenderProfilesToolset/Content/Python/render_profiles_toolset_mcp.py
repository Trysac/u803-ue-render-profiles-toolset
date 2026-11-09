"""Unreal MCP toolset that exposes ue_render_profiles_toolset to AI agents.

Discovered by the Toolset Registry at editor startup (this file lives in the plugin's
Content/Python). Every tool forwards to ``ue_render_profiles_toolset.mcp`` with the real ``unreal``
module and returns a JSON string whose first key is ``summary``. Mutating tools default to
``dry_run=True``. Only ``<cvar> <number>`` commands for CVars in the packaged catalog are sent;
console changes are not editor transactions (Ctrl+Z does not undo them): ``revert_last`` does.
"""

import toolset_registry
import unreal

from ue_render_profiles_toolset import mcp


@unreal.uclass()
class RenderProfileTools(unreal.ToolsetDefinition):
    """Apply, compare and revert versioned render profiles (CVars and scalability groups).

    Profiles are JSON files: built-in examples (balanced, lumen-lite-6gb, trailer-max) plus the
    project's Config/RenderProfiles/*.json, which override built-ins by name. Use it to try a
    render profile on the running editor safely (snapshot first, read-back check, one-call revert)
    and to generate DefaultScalability.ini for the game's Low/Medium/High presets. Only CVars in
    the packaged whitelist are ever sent; CVars missing in this engine or needing a restart are
    reported, not sent.
    """

    @staticmethod
    @toolset_registry.tool_call
    def list_profiles() -> str:
        """List every available render profile (read-only).

        Returns:
            JSON with summary and profiles (name, extends, note, target_hardware, cvar_count,
            source: builtin, project or snapshot).
        """
        return mcp.list_profiles(unreal)

    @staticmethod
    @toolset_registry.tool_call
    def describe_profile(name: str) -> str:
        """Resolve one profile through its extends chain and validate it (read-only).

        Args:
            name: Profile name as shown by list_profiles.

        Returns:
            JSON with summary, chain, note, target_hardware, cvars (merged values) and issues
            (unknown_cvar, invalid_type, out_of_range errors; restart_required warnings).
        """
        return mcp.describe_profile(unreal, name)

    @staticmethod
    @toolset_registry.tool_call
    def snapshot_current(name: str = "") -> str:
        """Read the live value of every whitelisted CVar.

        Args:
            name: Optional; when set, the values are kept as a profile with this name for the
                editor session (usable by diff_profiles and apply_profile). It may not reuse a
                built-in or project profile name or "current".

        Returns:
            JSON with summary, values, missing (CVars this engine does not expose) and, when
            name is set, saved_as.
        """
        return mcp.snapshot_current(unreal, name)

    @staticmethod
    @toolset_registry.tool_call
    def diff_profiles(left: str, right: str = "current") -> str:
        """Compare two profiles CVar by CVar, with the catalog impact note (read-only).

        Args:
            left: Profile name, or "current" for the live editor values.
            right: Profile name, or "current" (default) for the live editor values.

        Returns:
            JSON with summary, entries (cvar, left, right, impact) and missing.
        """
        return mcp.diff_profiles(unreal, left, right)

    @staticmethod
    @toolset_registry.tool_call
    def apply_profile(name: str, dry_run: bool = True) -> str:
        """Apply a profile to the running editor with whitelisted console commands.

        A real apply first stores a snapshot (for revert_last), runs sg.* groups before single
        CVars, then reads every written CVar back.

        Args:
            name: Profile name as shown by list_profiles.
            dry_run: When true (default) nothing is executed; the result lists the commands.

        Returns:
            JSON with summary, commands, commands_executed, skipped_restart (need a restart, not
            sent), missing_cvars (absent in this engine, not sent), mismatched and snapshot_id.
        """
        return mcp.apply_profile(unreal, name, dry_run)

    @staticmethod
    @toolset_registry.tool_call
    def revert_last(dry_run: bool = True) -> str:
        """Restore the CVar values recorded before the last real apply_profile.

        Args:
            dry_run: When true (default) nothing is executed; the result lists the commands.

        Returns:
            JSON with summary, snapshot_id, profile, commands, commands_executed and mismatched;
            error code nothing_to_revert when no snapshot is stored.
        """
        return mcp.revert_last(unreal, dry_run)

    @staticmethod
    @toolset_registry.tool_call
    def export_scalability_ini(levels_json: str, write: bool = False, dry_run: bool = True) -> str:
        """Render DefaultScalability.ini that maps quality levels to profiles.

        Args:
            levels_json: JSON object of level to profile name, levels Low, Medium, High, Epic
                or Cinematic, e.g. {"Low": "lumen-lite-6gb", "Medium": "balanced"}.
            write: Write Config/DefaultScalability.ini (only together with dry_run false).
            dry_run: When true (default) no file is written; the text is returned either way.

        Returns:
            JSON with summary, text, levels, skipped_cvars (no scalability group), written and
            path.
        """
        return mcp.export_scalability_ini(unreal, levels_json, write, dry_run)
