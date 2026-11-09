---
name: ue-render-profiles
description: Try, compare and revert Unreal Engine 5.8 render settings (Lumen, shadows, AA, screen percentage, streaming pool, sg.* scalability groups) through the RenderProfileTools MCP toolset, and generate DefaultScalability.ini for Low/Medium/High. Use whenever rendering quality or GPU cost must change in the editor; never type render CVars by hand.
---
# Render profiles (Unreal MCP toolset `RenderProfileTools`)

Requires the Render Profiles Toolset plugin enabled and the Unreal MCP server connected.

1. **Look:** `list_profiles`, then `describe_profile` for the candidate. Read `issues`
   (`restart_required` CVars are never applied live).
2. **Compare:** `diff_profiles` with `left` = profile and `right` = `"current"` to see what changes.
3. **Plan:** `apply_profile` with `dry_run: true`; read `commands`, `skipped_restart`, `missing_cvars`.
4. **Apply:** same call with `dry_run: false`. Check `mismatched` is empty. Tell the user the values
   are an example to validate on their hardware (`stat gpu`).
5. **Undo:** `revert_last` with `dry_run: false` restores every whitelisted CVar.
6. **Ship presets:** `export_scalability_ini` with `levels_json` like
   `{"Low": "lumen-lite-6gb", "Medium": "balanced", "High": "trailer-max"}`; write only with
   `write: true, dry_run: false` after the user agrees.

Rules: one MCP call at a time; use `snapshot_current` with a `name` before experimenting so the
starting point is a profile; project profiles go in `Config/RenderProfiles/<name>.json`; editor and
packaged-game scalability differ; if a result has `error`, read `error.code` and fix the input
instead of retrying blindly.
