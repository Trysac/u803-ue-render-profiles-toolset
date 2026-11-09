# Testing

## Running

```sh
uv run python scripts/check.py                    # every gate, as CI and the factory run it
uv run pytest --cov=ue_render_profiles_toolset   # tests with coverage report
uv run python tools/build_plugin.py               # build the Unreal plugin zip into dist/
```

## Policy

- Branch coverage of `src/ue_render_profiles_toolset` must stay at or above 85 %; the gate fails below it.
- Tests exercise the public API (`import ue_render_profiles_toolset`) and assert observable effects: return values, raised `ProfileError` codes and messages, and the console commands sent to the fake.
- Each bug fix starts with a failing test that reproduces it.
- Tests are deterministic: no network, no wall clock, no dependence on test order. Hypothesis properties run with `derandomize=True`.

## What the suite covers

The specification defines these tests; check them against the `tests/` folder before relying on a specific file name.

- `resolve_profile`: child values override parent values key by key; a cycle such as a -> b -> a raises `extends_cycle`.
- `validate_profile`: a CVar not in `catalog/cvars.json` is reported as `unknown_cvar`, not silently ignored.
- `diff_profiles`: `balanced` against `trailer-max` lists every differing CVar with both values and the impact note.
- `apply_profile` with `dry_run=True` on the fake console executes 0 commands and lists the plan.
- Apply with `dry_run=False` followed by `revert_last`: every whitelisted CVar equals its snapshot value.
- Every generated command names a whitelisted CVar.
- A read-back of `r.ScreenPercentage` as 75 after 100 was requested is listed under `mismatched`.
- `export_scalability_ini` for Low, Medium and High equals the golden file `tests/fixtures/golden/DefaultScalability.ini`, and a check confirms its file name matches the literal `tests/golden/DefaultScalability.ini` named in the specification.
- `export_scalability_ini` with `write=True` and `dry_run=True` writes 0 files.
- Property tests (Hypothesis, derandomized): merge is associative by levels; apply then revert restores the snapshot; no command falls outside the whitelist.

The fake console used by these tests is `tests/fakes/unreal.py`. None of these tests run inside Unreal.

## Tests in CI (no Unreal needed)

| File | What it covers |
|---|---|
| `tests/test_profile.py`, `tests/test_catalog_schema.py`, `tests/test_plan_diff_ini.py`, `tests/test_properties.py` | Pure core: `extends` resolution and cycles, catalog and schema validation, diff, plans, ini golden file, Hypothesis properties. |
| `tests/test_adapter.py` | Adapter against `tests/fakes/unreal.py` (dry runs, apply/revert, `sg.*` side effects, read-back mismatches, export paths). |
| `tests/test_mcp.py` | MCP layer: JSON with `summary` first, errors as data (`io_error`, `unreal_error` included), apply and revert across separate calls, revert after a simulated Python reload (session file in `Saved/`), unreadable or unwritable session files, missing CVars reported and not sent, restart CVars flagged and not sent, only whitelisted commands executed, project profiles overriding built-ins, bad project files, named snapshots, `current` diffs, ini export write rules. |
| `tests/test_session.py` | Snapshot store and session file round trip and rejection of malformed state. |
| `tests/test_plugin_shell.py` | Loads `plugin/.../Content/Python/render_profiles_toolset_mcp.py` with a fake `unreal` and a fake `toolset_registry`: the class is `RenderProfileTools`, every MCP function is a documented `tool_call` static method with typed primitive parameters returning `str`, and each forwards correctly. |
| `tests/test_build_plugin.py` | The plugin zip contains the `.uplugin`, the toolset module, the vendored package and its four `data/` JSON files; the extracted package imports in an isolated interpreter and loads its catalog and profiles; the `.uplugin` depends on `PythonScriptPlugin` and `ToolsetRegistry` and its version matches the package. |

## In-editor check (manual, Unreal Engine 5.8)

CI cannot run Unreal, so these steps are the acceptance test for the real engine. Never mark the
plugin as verified in Unreal without running them.

1. Install the plugin (README, "Install in Unreal Engine") in a blank UE 5.8 project.
2. Compare the decorator order in `render_profiles_toolset_mcp.py` (`@staticmethod` above
   `@toolset_registry.tool_call`) with the engine's own example,
   `Engine/Plugins/Experimental/ToolsetRegistry/Content/Python/toolset_registry/toolsets/core/actor.py`,
   and match it if it differs.
3. Enable Python *Developer Mode* (Editor Preferences > Plugins > Python), restart, and check in
   `Intermediate/PythonStub/unreal.py` that `SystemLibrary.get_console_variable_int_value`,
   `get_console_variable_float_value`, `execute_console_command`, `UnrealEditorSubsystem`
   (`get_editor_world`), `Paths.project_config_dir`, `Paths.project_saved_dir` and
   `ToolsetDefinition` exist. Note whether reading an unknown CVar raises or returns 0 (see
   ADR 0003): if it returns 0, missing CVars show up as `mismatched`, not `missing_cvars`.
4. Run `py "<repo>/tests/ue_smoke.py"` in the Output Log (Python). Open
   `Saved/Smoke/u803-ue-render-profiles-toolset.json`: every step must have `"ok": true`,
   including `all cvars restored`.
5. From the agent: `list_toolsets` shows `RenderProfileTools`; `describe_toolset` lists seven tools
   with their parameter descriptions; a dry-run `apply_profile` returns a summary.
6. Apply `lumen-lite-6gb` with `dry_run=false`, verify with `stat gpu` that the GPU cost changes,
   then `revert_last` with `dry_run=false` and confirm with `snapshot_current` that every value is
   back.
7. Run `ModelContextProtocol.RefreshTools` (or `importlib.reload` the toolset module) between the
   apply and the revert once, to confirm the revert is read back from
   `Saved/RenderProfilesToolset/session.json`.
8. Put a copy of `balanced.json` with one changed value in `Config/RenderProfiles/` and confirm
   `list_profiles` reports it with `source: "project"`.
9. Export the ini with `write=true, dry_run=false` in the blank project, restart and confirm it
   loads without errors in the log; test it in a packaged build as well. Record the date, engine
   version and result in `docs/PROJECT.md`.

## Not covered

Console platform profiles, hardware ray tracing, and behavior on engine versions other than 5.8.

## Tiers

- Local tier (every gate run, coverage measured here): unit and property tests, plus conformance on small fixtures kept in the repository.
- CI tier: conformance that needs an external tool or a download. These are marked `@pytest.mark.conformance`; `scripts/check.py` deselects them locally unless `FABRICA_CI=1` is set.

## Layout

`tests/test_<module>.py` mirrors each public module. Shared fixtures go in `tests/conftest.py`. The fake console lives in `tests/fakes/`, and golden files live under `tests/fixtures/`.
