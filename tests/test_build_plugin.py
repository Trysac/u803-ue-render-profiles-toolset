"""The plugin build vendors the package (with its data files) next to the toolset module."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
import ue_render_profiles_toolset as pkg
from ue_render_profiles_toolset import load_catalog, load_profiles, mcp
class Paths:
    @staticmethod
    def project_config_dir():
        raise RuntimeError("no project")
    project_saved_dir = project_config_dir
class UE:
    Paths = Paths
listing = json.loads(mcp.list_profiles(UE()))
print(json.dumps({"file": pkg.__file__, "cvars": len(load_catalog().cvars),
                  "profiles": sorted(load_profiles()), "listed": len(listing["profiles"])}))
"""


def _load() -> Any:
    spec = importlib.util.spec_from_file_location(
        "build_plugin", ROOT / "tools" / "build_plugin.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_creates_installable_zip(tmp_path: Path) -> None:
    bp = _load()
    archive = bp.build(ROOT, tmp_path)
    plugin = bp.find_plugin(ROOT).name
    package = bp.find_package(ROOT).name
    names = set(zipfile.ZipFile(archive).namelist())
    assert f"{plugin}/{plugin}.uplugin" in names
    assert f"{plugin}/Content/Python/{package}/__init__.py" in names
    assert f"{plugin}/Content/Python/{package}/core/__init__.py" in names
    assert any(n.startswith(f"{plugin}/Content/Python/") and n.endswith("_mcp.py") for n in names)
    assert not any("__pycache__" in n for n in names)


def test_zip_ships_the_data_files(tmp_path: Path) -> None:
    bp = _load()
    archive = bp.build(ROOT, tmp_path)
    plugin = bp.find_plugin(ROOT).name
    package = bp.find_package(ROOT)
    names = set(zipfile.ZipFile(archive).namelist())
    data = sorted(p for p in (package / "data").rglob("*.json"))
    assert len(data) == 4
    for path in data:
        relative = path.relative_to(package.parent).as_posix()
        assert f"{plugin}/Content/Python/{relative}" in names, relative


def test_vendored_package_loads_its_data_in_isolation(tmp_path: Path) -> None:
    bp = _load()
    archive = bp.build(ROOT, tmp_path / "dist")
    target = tmp_path / "Plugins"
    zipfile.ZipFile(archive).extractall(target)
    content = target / bp.find_plugin(ROOT).name / "Content" / "Python"
    probe = tmp_path / "probe.py"
    probe.write_text(PROBE, encoding="utf-8")
    out = subprocess.run(
        [sys.executable, "-I", str(probe), str(content)],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    report = json.loads(out.stdout)
    assert Path(report["file"]).is_relative_to(content)
    assert report["cvars"] == 12
    assert report["profiles"] == ["balanced", "lumen-lite-6gb", "trailer-max"]
    assert report["listed"] == 3


def test_uplugin_is_valid_and_depends_on_registry() -> None:
    bp = _load()
    plugin = bp.find_plugin(ROOT)
    assert plugin.name == "RenderProfilesToolset"
    data = json.loads((plugin / f"{plugin.name}.uplugin").read_text(encoding="utf-8"))
    deps = {p["Name"] for p in data["Plugins"]}
    assert {"PythonScriptPlugin", "ToolsetRegistry"} <= deps
    version = bp.read_version(bp.find_package(ROOT))
    assert data["VersionName"] == version == "0.2.0"
