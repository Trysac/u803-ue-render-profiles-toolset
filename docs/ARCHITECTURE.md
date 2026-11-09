# Architecture

## Purpose

`trysac-ue-render-profiles-toolset` (import name `ue_render_profiles_toolset`) provides versioned Unreal Engine render profiles. A pure core resolves, validates, diffs and plans profile changes. A thin adapter applies those plans through the Unreal Python API, and the package includes a packaged CVar catalog and three example profiles.

## Shape

```text
AI agent --MCP--> Unreal MCP server --> Toolset Registry
                                            |
   plugin/RenderProfilesToolset/Content/Python/render_profiles_toolset_mcp.py  (RenderProfileTools)
                                            |  forwards with the real unreal module
                                            v
   ue_render_profiles_toolset.mcp      flat params in, JSON string out, errors as data
          |                  \
          |                   session.py  snapshot stack + named snapshots
          |                               (module level, mirrored to Saved/RenderProfilesToolset/)
          v
   ue_render_profiles_toolset.adapter  reads/writes CVars through ue; loads project profiles
          |
          v
   core/  pure: profile, schema, catalog, diff, plan, ini     data/  catalog + example profiles
```

Library callers can use the adapter directly (public API in `__init__.py`); `results.py` and
`errors.py` hold the result dataclasses and `ProfileError`.

- **Pure core** (`core/`): never imports `unreal`. It resolves `extends` chains with cycle detection, validates profiles against the catalog, computes diffs, and builds apply and revert plans and the scalability ini text.
- **Adapter** (`adapter.py`): every public function takes `ue` as its first argument. It reads CVars with `ue.SystemLibrary.get_console_variable_int_value` and `get_console_variable_float_value`, and writes them with `ue.SystemLibrary.execute_console_command`, passing the editor world from `get_editor_subsystem(UnrealEditorSubsystem)`. It reads the project config folder from `ue.Paths.project_config_dir()`, loads project profiles from `Config/RenderProfiles/*.json` on top of the packaged ones (same name: project wins), and reports CVars whose read fails as missing instead of dropping them.
- **Data**: the CVar catalog (`cvars.json`) and the example profiles are packaged with the library.
- **Public API**: the names listed in `__all__` of `src/ue_render_profiles_toolset/__init__.py`. Anything else is internal.

## Errors

Invalid profiles, unknown profiles, extends cycles, non-whitelisted commands and missing snapshots raise `ProfileError` with a stable `code`. Input that fails type checks in the core raises `ProfileError` with code `invalid_profile`.

## Side effects

The core has no I/O and no global state, apart from the process-wide default snapshot store used by the adapter when no `store` is passed. The adapter performs console reads and writes through `ue` and reads `Config/RenderProfiles/*.json`. Its only file write is `DefaultScalability.ini` inside a `Config` folder, and only when `write=True` and `dry_run=False`. The `session` module (used by `mcp`) writes `Saved/RenderProfilesToolset/session.json` after each real apply, real revert and named snapshot.

## Unreal integration

- `plugin/RenderProfilesToolset/RenderProfilesToolset.uplugin` declares a Python-only editor plugin
  that depends on `PythonScriptPlugin` and `ToolsetRegistry`.
- `plugin/RenderProfilesToolset/Content/Python/render_profiles_toolset_mcp.py` defines
  `RenderProfileTools(unreal.ToolsetDefinition)`; each tool is a static method marked with
  `@toolset_registry.tool_call`, with Google-style docstrings that the registry turns into the tool
  schema. It contains no logic: it forwards to `mcp.py`.
- Each MCP call is a separate, short call on the game thread. State shared between calls (the
  snapshot stack used by `revert_last`, named snapshots) lives at module level in `session.py` and
  is mirrored to `Saved/RenderProfilesToolset/session.json`, so it survives a Python reload.
- Console commands are not editor transactions, so `ScopedEditorTransaction` is not used and Ctrl+Z
  does not undo them; `revert_last` is the undo.
- `tools/build_plugin.py` copies the plugin and vendors the package, including `data/`, into
  `Content/Python/`; the package reads its data with `importlib.resources`, which works from that
  folder without pip.
- No compatibility layer is needed: the adapter uses `SystemLibrary` console functions,
  `UnrealEditorSubsystem.get_editor_world` and `Paths`, none of them deprecated in UE 5.x.
- The real-engine check is `tests/ue_smoke.py` plus the manual steps in `docs/TESTING.md`.

## Decisions

Architecture decisions are recorded in [decisions/](decisions/) as numbered ADRs (0002: pure core
with whitelisted numeric commands; 0003: plugin shell, JSON results and session persistence).
