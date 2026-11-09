# Python plugin shell with JSON string results and persisted session state

Status: accepted (pending verification in Unreal Engine 5.8)

## Context

The package must become an Unreal MCP toolset: a `unreal.ToolsetDefinition` subclass in a plugin's
`Content/Python/`, discovered by the Toolset Registry. The registry is experimental and its handling
of complex parameter and return types is not documented in detail. Each MCP call is a separate call
on the game thread, yet `revert_last` must undo an `apply_profile` made in an earlier call, and
should still work after the editor reloads its Python modules. Nothing can run in CI inside Unreal.

## Decision

- Ship a Python-only plugin (`plugin/RenderProfilesToolset/`) whose toolset module only forwards to
  a new `mcp.py` layer. All behavior stays in the package, so it is covered by CI.
- Tools take primitive parameters (str, bool); the level map of `export_scalability_ini` travels as
  a JSON string. Every tool returns a JSON string whose first key is `summary`; errors are returned
  as data, never raised to the agent.
- Every mutating tool defaults to `dry_run=true`, including `revert_last` (the library function
  keeps its `dry_run=False` default for existing callers).
- Snapshots and named snapshots live in a module-level session (`session.py`) and are written to
  `<Project>/Saved/RenderProfilesToolset/session.json` after each change; the file is read back the
  first time a session is needed after a reload.
- Project profiles are read from `<Project>/Config/RenderProfiles/*.json` and override built-ins by
  name; the name `current` is reserved for the live editor values.
- No `ScopedEditorTransaction`: console variable changes are not transactable, so `revert_last` is
  the undo mechanism.
- `tools/build_plugin.py` vendors the package and its `data/` into the plugin; no pip in the editor.

## Consequences

The schema the agent sees is simple and certain to be supported, at the cost of the agent parsing
JSON from a string. The session file outlives an editor restart while console values do not, so a
revert after a restart only re-sends the recorded values that differ. Whether the engine raises or
returns 0 for an unknown CVar is unverified: in the second case missing CVars appear as `mismatched`
rather than `missing_cvars`. The decorator order and the API names are confirmed by the manual steps
in `docs/TESTING.md`.
