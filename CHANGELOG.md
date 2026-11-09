# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-11-08

### Added

- Unreal plugin `plugin/RenderProfilesToolset/` (Python only): `RenderProfileTools` toolset registered in the Toolset Registry with seven documented tools.
- `mcp` module: flat parameters, JSON string results with `summary` first, errors returned as data (`io_error` and `unreal_error` besides the library codes).
- `session` module: the snapshot stack and named snapshots persist across MCP calls (module level) and in `Saved/RenderProfilesToolset/session.json`, so `revert_last` survives a Python reload.
- Project profiles from `<Project>/Config/RenderProfiles/*.json` (override built-ins by name; `load_project_profiles`, `load_registry`); `list_profiles` reports each profile's `source`.
- CVars this engine version does not expose are reported (`missing` in snapshots and diffs, `missing_cvars` in apply) and never sent.
- `diff_profiles` accepts `current` (live editor values) on either side; `snapshot_current` can keep the values as a named session profile.
- `tools/build_plugin.py` (plugin zip with the vendored package and its data files), `tests/ue_smoke.py` (in-editor check), `skill/SKILL.md`, ADR 0003.

### Changed

- `docs/AGENT_USAGE.md` describes real `call_tool` usage; `docs/TESTING.md` lists the in-editor acceptance steps.
- The MCP `revert_last` tool defaults to `dry_run=true` like every other mutating tool (the library function keeps `dry_run=False`).

## [0.1.0] - 2026-11-08

### Added

- Add the pure core (profile resolution with cycle detection, catalog validation, diff, apply/revert plans, scalability ini export), a thin Unreal adapter, a CVar catalog and three example render profiles.
- Initial project structure from the factory utility template.
