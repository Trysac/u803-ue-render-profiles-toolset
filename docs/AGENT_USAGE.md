# Agent usage

This package is the pure core and the adapter of an Unreal MCP toolset for versioned render profiles. The plugin that registers the `ToolsetDefinition` class (`@unreal.uclass()`, `@toolset_registry.tool_call` static methods) is built separately; the adapter functions below are what its tools call. Every function takes the `unreal` module first.

The adapter was tested against a fake console only. Nothing in this repository was tested inside Unreal Engine.

## Tools and examples

```
call_tool("list_profiles", {})
call_tool("describe_profile", {"name": "lumen-lite-6gb"})
call_tool("snapshot_current", {})
call_tool("diff_profiles", {"left": "balanced", "right": "trailer-max"})
call_tool("apply_profile", {"name": "lumen-lite-6gb", "dry_run": true})
call_tool("apply_profile", {"name": "lumen-lite-6gb", "dry_run": false})
call_tool("revert_last", {})
call_tool("export_scalability_ini", {"levels": {"Low": "lumen-lite-6gb", "Medium": "balanced", "High": "trailer-max"}})
call_tool("export_scalability_ini", {"levels": {"Medium": "balanced"}, "write": true, "dry_run": false})
```

Every result is a dataclass with a one-line `summary`; `ue_render_profiles_toolset.results.to_dict` converts it to plain data. Errors are `ProfileError` with a `code`: `extends_cycle`, `unknown_profile`, `invalid_profile`, `nothing_to_revert`.

## Safety rules

- `apply_profile` defaults to `dry_run=True`: no console command is executed and the plan lists each command.
- Commands have the single shape `<cvar> <number>` and only name CVars of `data/catalog/cvars.json`.
- Read-only or startup CVars (for example `r.Shadow.Virtual.Enable`) are never sent; they are listed in `skipped_restart`.
- `sg.*` commands run first because a scalability group re-applies its own CVars.
- After applying, every written CVar is read back; differences are listed under `mismatched`.
- Files are written only by `export_scalability_ini` with `write=True` and `dry_run=False`, as `DefaultScalability.ini` inside a folder named `Config`.
- Snapshots live in memory (at most 16); a restart of the editor loses them.

## Catalog and profiles

Catalog entries carry the type, the documented range (`not documented` when the documentation states none), a description, an impact note, a source link, warnings and a restart flag. Source links point to section-level pages of the official Unreal documentation; confirm the exact CVar entry there. The `scalability_group` of each entry is declared by this catalog to drive the ini export and is not taken from Epic documentation; check it against your project's `BaseScalability.ini`.

The three packaged profiles (`balanced`, `lumen-lite-6gb`, `trailer-max`) are examples: example, validate on your hardware.

## Editor versus packaged game

Scalability in the editor and in a packaged game differ. Values applied with console commands affect the running session only; test the exported ini in a packaged build.

## Out of scope

Automatic optimization, console platform profiles and hardware ray tracing.
