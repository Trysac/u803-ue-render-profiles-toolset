# ue-render-profiles-toolset

[![PyPI version](https://img.shields.io/pypi/v/trysac-ue-render-profiles-toolset)](https://pypi.org/project/trysac-ue-render-profiles-toolset/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-ue-render-profiles-toolset)](LICENSE)
[![CI](https://github.com/Trysac/u803-ue-render-profiles-toolset/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u803-ue-render-profiles-toolset/actions/workflows/ci.yml)

Versioned Unreal Engine render profiles (CVars and scalability): a pure core with profile resolution, catalog validation, diff, apply and revert plans, and a thin adapter for the Unreal Python API.

## Problem

Tuning Unreal Engine 5.8 rendering for a target GPU means typing console variables by hand, with no record, no safe revert and no link to the game's Low/Medium/High presets. This library gives agents declared, diffable, reversible profiles. The packaged example profiles are marked "example, validate on your hardware", and editor and packaged-game scalability differ. The plugin and the adapter are tested in CI against fakes; they have not yet been verified inside Unreal.

## Install in Unreal Engine (the MCP toolset)

1. Build the plugin: `uv run python tools/build_plugin.py` (or download the zip from a release). It
   creates `dist/RenderProfilesToolset-<version>.zip`, with the package, its CVar catalog and the
   example profiles vendored into `Content/Python/`.
2. Unzip it into `<YourProject>/Plugins/` (you get `Plugins/RenderProfilesToolset/`).
3. In the editor enable **Unreal MCP**, **All Toolsets** and **Render Profiles Toolset**, restart,
   and turn on *Editor Preferences > General > Model Context Protocol > Auto Start Server*.
4. Run `ModelContextProtocol.GenerateClientConfig ClaudeCode` in the console (writes `.mcp.json`),
   then start your agent from the project root. If the editor was already running, run
   `ModelContextProtocol.RefreshTools`.
5. The agent finds the toolset `RenderProfileTools` through `list_toolsets` and calls it with
   `call_tool`. See [docs/AGENT_USAGE.md](docs/AGENT_USAGE.md) and the optional Claude Code skill in
   [skill/SKILL.md](skill/SKILL.md).
6. Optional: add your own profiles as `<YourProject>/Config/RenderProfiles/<name>.json` (same
   format as the packaged ones; a project profile overrides a built-in with the same name).

Tools: `list_profiles`, `describe_profile`, `snapshot_current`, `diff_profiles`, `apply_profile`,
`revert_last`, `export_scalability_ini`. Snapshots for `revert_last` persist across MCP calls and
are mirrored to `<YourProject>/Saved/RenderProfilesToolset/session.json`.

Requirements: Unreal Engine 5.8 with the experimental Unreal MCP and Toolset Registry plugins.
Python only, nothing to compile. Status: the logic, the MCP layer and the plugin shell are tested in
CI against a fake `unreal` module; the in-editor check is `tests/ue_smoke.py` (see
[docs/TESTING.md](docs/TESTING.md)).

## Install as a Python library

```sh
pip install trysac-ue-render-profiles-toolset
# or
uv add trysac-ue-render-profiles-toolset
```

Requires Python 3.11 or newer. No runtime dependencies.

## Usage

```python
from ue_render_profiles_toolset import (
    load_catalog,
    load_profiles,
    resolve_profile,
    validate_profile,
)

profiles = load_profiles()
profile = resolve_profile("lumen-lite-6gb", profiles)
issues = validate_profile(profile, load_catalog())
print(profile.name, len(profile.cvars), len(issues))
```

Adapter functions take the `unreal` module (or a fake with the same attributes) as their first argument, for example `apply_profile(unreal, "lumen-lite-6gb", dry_run=True)`. `apply_profile` defaults to `dry_run=True`, which executes no console command.

`ue_render_profiles_toolset.mcp` exposes the same seven operations with flat, JSON-friendly
parameters and a JSON string result (first key `summary`; errors come back as
`{"summary": "error: ...", "error": {...}}` instead of raising). The plugin's toolset class
forwards to it. Its `revert_last` defaults to `dry_run=True`.

## Public API

Pure core (no `unreal` import): `load_catalog`, `load_profiles`, `resolve_profile`, `validate_profile`, `Profile`.

Profile loading (takes `ue`): `load_project_profiles(ue)` reads `Config/RenderProfiles/*.json`; `load_registry(ue, captured=None)` returns built-in, then project, then captured profiles (later wins by name). Adapter functions use `load_registry(ue)` when `profiles` is None.

Adapter (each takes `ue` first): `list_profiles`, `describe_profile`, `snapshot_current`, `diff_profiles`, `apply_profile`, `revert_last`, `export_scalability_ini`. Each returns a result dataclass with a one-line `summary` field.

- `apply_profile(ue, name, dry_run=True, profiles=None, store=None)`: plans the whitelisted `<cvar> <number>` commands. When not dry-running, it stores a snapshot, executes the commands, reads each written CVar back, and lists differing values under `mismatched`. `sg.*` commands run first. Read-only or startup CVars are never sent and are listed in `skipped_restart`.
- `revert_last(ue, dry_run=False, store=None)`: restores every snapshot value that differs from the current value.
- `export_scalability_ini(ue, levels, config_dir=None, write=False, dry_run=True, profiles=None)`: renders `DefaultScalability.ini`. A file is written only when `write=True` and `dry_run=False`, and only as `DefaultScalability.ini` inside a folder named `Config` (default: the project's Config folder).
- `diff_profiles(ue, left, right, profiles=None)`: lists every CVar whose value differs, with the catalog impact note. Either side may be `"current"` (live values).
- CVars that cannot be read in this engine version are reported: `missing` in `snapshot_current` and `diff_profiles`, `missing_cvars` in `apply_profile` (no command is sent for them).

Errors: `ProfileError` carries a `code` and a `message` of at most 200 characters. Codes: `extends_cycle`, `unknown_profile`, `invalid_profile`, `nothing_to_revert`.

Limits: the catalog holds at most 512 entries, the profile registry at most 64 profiles, and the snapshot store keeps at most 16 snapshots. The library's default store is in memory only; the `mcp` layer mirrors its store to the project's `Saved/` folder. Only CVars listed in the catalog can be read or written.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
