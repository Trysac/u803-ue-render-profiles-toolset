# Agent usage

Once the plugin is enabled, the Unreal MCP server lists the toolset `RenderProfileTools`. With the
default *tool search* mode the agent sees three meta-tools: `list_toolsets`, `describe_toolset` and
`call_tool`. Calls run one at a time on the editor's game thread: never issue them in parallel.

Every tool returns a JSON string. The first key is always `summary` (one line). Errors are data:
`{"summary": "error: ...", "error": {"code": "...", "message": "..."}}` with codes
`unknown_profile`, `extends_cycle`, `invalid_profile`, `nothing_to_revert`, `io_error` or
`unreal_error`. Mutating tools (`apply_profile`, `revert_last`, `export_scalability_ini`) default to
`dry_run: true`: call once to see the plan, then again with `false`.

The responses below come from the CI fake console; values in a real editor differ. The plugin has
not yet been verified inside Unreal.

## Typical flow

1. `snapshot_current` with `name: "before-test"` to keep the starting point as a profile.
2. `diff_profiles` with `left: "lumen-lite-6gb"` (right defaults to `"current"`).
3. `apply_profile` dry run, then `dry_run: false`; check `mismatched`, `skipped_restart`, `missing_cvars`.
4. Check the result in the viewport (`stat gpu`); `revert_last` with `dry_run: false` to undo.
5. `export_scalability_ini` to map Low/Medium/High to profiles for the shipped game.

## list_profiles and describe_profile

```json
{"toolset": "RenderProfileTools", "tool": "list_profiles", "arguments": {}}
```

```json
{"summary": "3 profiles available", "profiles": [{"name": "balanced", "extends": null, "note": "example, validate on your hardware", "target_hardware": "example, validate on your hardware", "cvar_count": 10, "source": "builtin"}, "..."]}
```

`source` is `builtin` (packaged), `project` (`<Project>/Config/RenderProfiles/<name>.json`, which
overrides a built-in with the same name) or `snapshot` (kept by `snapshot_current` with a name).
`describe_profile` (`{"name": "lumen-lite-6gb"}`) returns the `chain` (`["lumen-lite-6gb",
"balanced"]`), the merged `cvars` and `issues` such as `restart_required` for
`r.Shadow.Virtual.Enable`.

## snapshot_current and diff_profiles

```json
{"toolset": "RenderProfileTools", "tool": "diff_profiles", "arguments": {"left": "lumen-lite-6gb", "right": "current"}}
```

```json
{"summary": "5 cvars differ between lumen-lite-6gb and current", "left": "lumen-lite-6gb", "right": "current",
 "entries": [{"cvar": "r.ScreenPercentage", "left": 75, "right": 100.0, "impact": "not documented"}, "..."], "missing": []}
```

`snapshot_current` returns `values` for every whitelisted CVar and `missing` for CVars this engine
does not expose. With `{"name": "before-test"}` the values are kept as a session profile
(`saved_as`), which `diff_profiles` and `apply_profile` accept like any other profile.

## apply_profile

```json
{"toolset": "RenderProfileTools", "tool": "apply_profile", "arguments": {"name": "lumen-lite-6gb", "dry_run": false}}
```

```json
{"summary": "Applied lumen-lite-6gb: 9 commands executed, 0 mismatched", "profile": "lumen-lite-6gb", "dry_run": false,
 "commands": ["sg.GlobalIlluminationQuality 1", "sg.ShadowQuality 1", "r.AntiAliasingMethod 4", "..."],
 "commands_executed": 9, "skipped_restart": ["r.Shadow.Virtual.Enable"], "mismatched": [], "mismatch_details": [],
 "snapshot_id": 1, "missing_cvars": [], "persisted": true,
 "state_file": "C:/Projects/MyGame/Saved/RenderProfilesToolset/session.json"}
```

- Only `<cvar> <number>` commands for CVars in the packaged catalog are sent; `sg.*` groups first.
- `skipped_restart`: read-only or startup CVars; set them in config and restart the editor.
- `missing_cvars`: CVars of the profile this engine version does not expose; no command is sent.
- `mismatched`: CVars whose read-back value differs from the request.
- `persisted: false` with `state_warning` means the session file could not be written; the
  snapshot still exists in memory for this editor session.

## revert_last

```json
{"toolset": "RenderProfileTools", "tool": "revert_last", "arguments": {"dry_run": false}}
```

```json
{"summary": "Reverted snapshot 1: 5 commands executed", "snapshot_id": 1, "profile": "lumen-lite-6gb", "dry_run": false,
 "commands": ["r.AntiAliasingMethod 1", "..."], "commands_executed": 5, "mismatched": [], "mismatch_details": [], "persisted": true, "state_file": "..."}
```

It restores every whitelisted CVar recorded before the last real apply (also those an `sg.*` group
changed as a side effect). Snapshots stack (at most 16): call again to undo the previous apply.
With no snapshot: `{"summary": "error: no snapshot to revert to", "error": {"code": "nothing_to_revert", ...}}`.
The stack survives a Python reload (it is re-read from `Saved/RenderProfilesToolset/session.json`);
after an editor restart the console values are back to config defaults, so a revert re-sends only
the recorded values that differ.

## export_scalability_ini

```json
{"toolset": "RenderProfileTools", "tool": "export_scalability_ini", "arguments": {
  "levels_json": "{\"Low\": \"lumen-lite-6gb\", \"Medium\": \"balanced\", \"High\": \"trailer-max\"}"}}
```

```json
{"summary": "Rendered DefaultScalability.ini with 3 levels, 0 files written", "text": "; Generated by ue-render-profiles-toolset. ...\n[GlobalIlluminationQuality@0]\n...",
 "levels": {"Low": "lumen-lite-6gb", "Medium": "balanced", "High": "trailer-max"}, "skipped_cvars": ["..."], "dry_run": true, "written": false, "path": null}
```

Add `"write": true, "dry_run": false` to write `<Project>/Config/DefaultScalability.ini` (the only
file it can write). `skipped_cvars` lists CVars without a scalability group. Editor and
packaged-game scalability differ: test the ini in a packaged build.

## Catalog and profiles

Catalog entries carry the type, the documented range (`not documented` when the documentation
states none), a description, an impact note, a source link, warnings and a restart flag. The
`scalability_group` of each entry is declared by this catalog and must be checked against the
project's `BaseScalability.ini`. The packaged profiles are examples: validate on your hardware.
