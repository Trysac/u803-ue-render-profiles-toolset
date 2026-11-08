# Architecture

## Purpose

`trysac-ue-render-profiles-toolset` (import name `ue_render_profiles_toolset`) provides versioned Unreal Engine render profiles. A pure core resolves, validates, diffs and plans profile changes. A thin adapter applies those plans through the Unreal Python API, and the package includes a packaged CVar catalog and three example profiles.

## Shape

```text
caller code --> ue_render_profiles_toolset (public API in __init__.py)
                    |
                    +-- core/ (pure: profile, schema, catalog, diff, plan, ini)
                    +-- adapter.py (reads and writes CVars through the ue object)
                    +-- results.py, errors.py (dataclasses and ProfileError)
```

- **Pure core** (`core/`): never imports `unreal`. It resolves `extends` chains with cycle detection, validates profiles against the catalog, computes diffs, and builds apply and revert plans and the scalability ini text.
- **Adapter** (`adapter.py`): every public function takes `ue` as its first argument. It reads CVars with `ue.SystemLibrary.get_console_variable_int_value` and `get_console_variable_float_value`, and writes them with `ue.SystemLibrary.execute_console_command`, passing the editor world from `get_editor_subsystem(UnrealEditorSubsystem)`. It reads the project config folder from `ue.Paths.project_config_dir()`.
- **Data**: the CVar catalog (`cvars.json`) and the example profiles are packaged with the library.
- **Public API**: the names listed in `__all__` of `src/ue_render_profiles_toolset/__init__.py`. Anything else is internal.

## Errors

Invalid profiles, unknown profiles, extends cycles, non-whitelisted commands and missing snapshots raise `ProfileError` with a stable `code`. Input that fails type checks in the core raises `ProfileError` with code `invalid_profile`.

## Side effects

The core has no I/O and no global state, apart from the process-wide default snapshot store used by the adapter when no `store` is passed. The adapter performs console reads and writes through `ue`. Its only file write is `DefaultScalability.ini` inside a `Config` folder, and only when `write=True` and `dry_run=False`.

## Decisions

Architecture decisions are recorded in [decisions/](decisions/) as numbered ADRs.
