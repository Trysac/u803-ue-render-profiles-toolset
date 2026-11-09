"""In-editor smoke test (NOT collected by pytest). Run inside Unreal Editor 5.8 with the plugin on.

Output Log > Cmd > Python:  py "<repo>/tests/ue_smoke.py"
It writes ``<Project>/Saved/Smoke/u803-ue-render-profiles-toolset.json`` with one entry per step.
It changes CVars of the running editor only between "apply real" and "revert real" and checks that
every whitelisted CVar is back to its starting value. It writes no Config file (the ini export is a
dry run) and it never deletes anything. The session file under
``Saved/RenderProfilesToolset/`` is updated by the real apply and revert.
"""

import json
import time
import traceback
from pathlib import Path

import unreal

REPO = "u803-ue-render-profiles-toolset"
PROFILE = "lumen-lite-6gb"
LEVELS = {"Low": "lumen-lite-6gb", "Medium": "balanced", "High": "trailer-max"}


def main() -> None:
    from ue_render_profiles_toolset import mcp

    out_dir = Path(unreal.Paths.project_saved_dir()) / "Smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    memo = {}

    def step(name, fn):
        started = time.time()
        try:
            value = fn()
            parsed = json.loads(value) if isinstance(value, str) else value
            ok = not (isinstance(parsed, dict) and "error" in parsed)
            results.append({"step": name, "ok": ok, "result": parsed})
        except Exception:  # the smoke test records every failure instead of stopping
            results.append({"step": name, "ok": False, "error": traceback.format_exc()[-2000:]})
        results[-1]["seconds"] = round(time.time() - started, 3)
        return results[-1].get("result")

    def unchanged():
        after = json.loads(mcp.snapshot_current(unreal))["values"]
        before = memo.get("before", {})
        changed = {
            k: [before.get(k), after.get(k)] for k in before if before.get(k) != after.get(k)
        }
        if changed:
            return {
                "error": {"code": "not_restored", "message": "cvars differ"},
                "changed": changed,
            }
        return {"summary": f"{len(before)} cvars equal to the starting snapshot"}

    step(
        "api: console and paths",
        lambda: {
            "summary": "api names resolved",
            "get_int": hasattr(unreal.SystemLibrary, "get_console_variable_int_value"),
            "get_float": hasattr(unreal.SystemLibrary, "get_console_variable_float_value"),
            "execute": hasattr(unreal.SystemLibrary, "execute_console_command"),
            "editor_subsystem": hasattr(unreal, "UnrealEditorSubsystem"),
            "config_dir": str(unreal.Paths.project_config_dir()),
        },
    )
    step(
        "toolset module imports",
        lambda: {"module": __import__("render_profiles_toolset_mcp").__name__},
    )
    step("list profiles", lambda: mcp.list_profiles(unreal))
    snap = step("snapshot", lambda: mcp.snapshot_current(unreal))
    memo["before"] = (snap or {}).get("values", {})
    step("describe", lambda: mcp.describe_profile(unreal, PROFILE))
    step("diff vs current", lambda: mcp.diff_profiles(unreal, PROFILE, "current"))
    step("apply dry run", lambda: mcp.apply_profile(unreal, PROFILE))
    step("apply real", lambda: mcp.apply_profile(unreal, PROFILE, dry_run=False))
    step("revert dry run", lambda: mcp.revert_last(unreal))
    step("revert real", lambda: mcp.revert_last(unreal, dry_run=False))
    step("all cvars restored", unchanged)
    step("export ini dry run", lambda: mcp.export_scalability_ini(unreal, json.dumps(LEVELS)))

    report = {
        "repo": REPO,
        "engine": unreal.SystemLibrary.get_engine_version(),
        "passed": sum(r["ok"] for r in results),
        "total": len(results),
        "steps": results,
    }
    target = out_dir / f"{REPO}.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    unreal.log(f"[smoke] {REPO}: {report['passed']}/{report['total']} ok -> {target}")


main()
