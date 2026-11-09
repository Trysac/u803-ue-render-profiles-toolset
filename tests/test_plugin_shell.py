"""The Content/Python toolset module forwards every tool to the MCP layer with ``unreal``."""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fakes.unreal import make_fake

from ue_render_profiles_toolset.session import reset_session

ROOT = Path(__file__).resolve().parents[1]
SHELLS = sorted((ROOT / "plugin").glob("*/Content/Python/*_mcp.py"))


@pytest.fixture
def shell(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    reset_session()
    fake = make_fake()
    fake.uclass = lambda: lambda cls: cls  # type: ignore[attr-defined]
    fake.ToolsetDefinition = type("ToolsetDefinition", (), {})  # type: ignore[attr-defined]
    registry = types.ModuleType("toolset_registry")
    registry.tool_call = lambda fn: setattr(fn, "is_tool", True) or fn  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "unreal", fake)
    monkeypatch.setitem(sys.modules, "toolset_registry", registry)
    assert len(SHELLS) == 1
    spec = importlib.util.spec_from_file_location("shell_under_test", SHELLS[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module, fake
    reset_session()


def _toolset(module: Any) -> Any:
    classes = [
        c for _, c in inspect.getmembers(module, inspect.isclass) if c.__module__ == module.__name__
    ]
    assert len(classes) == 1
    return classes[0]


def test_toolset_class_is_named_and_documented(shell: Any) -> None:
    module, _ = shell
    toolset = _toolset(module)
    assert toolset.__name__ == "RenderProfileTools"
    assert "render profiles" in (inspect.getdoc(toolset) or "")


def test_every_mcp_function_is_a_documented_tool(shell: Any) -> None:
    module, _ = shell
    toolset = _toolset(module)
    from ue_render_profiles_toolset import mcp

    public = {
        n
        for n, f in inspect.getmembers(mcp, inspect.isfunction)
        if f.__module__ == mcp.__name__ and not n.startswith("_") and n != "to_json"
    }
    tools = {n for n, f in vars(toolset).items() if isinstance(f, staticmethod)}
    assert public == tools
    for name in tools:
        fn = getattr(toolset, name)
        assert getattr(fn, "is_tool", False), name
        doc = inspect.getdoc(fn) or ""
        params = inspect.signature(fn).parameters
        assert "Args:" in doc or not params, name
        for param in params:
            assert f"{param}:" in doc, (name, param)
        assert "Returns:" in doc, name
        assert inspect.signature(fn).return_annotation in (str, "str")
        assert "ue" not in params
        mcp_params = list(inspect.signature(getattr(mcp, name)).parameters)[1:]
        assert list(params) == mcp_params, name
        for param in params.values():
            assert param.annotation in (str, bool, "str", "bool"), (name, param)


def test_tools_forward_with_unreal(shell: Any) -> None:
    module, fake = shell
    toolset = _toolset(module)
    assert len(json.loads(toolset.list_profiles())["profiles"]) == 3
    assert json.loads(toolset.describe_profile("balanced"))["name"] == "balanced"
    assert "values" in json.loads(toolset.snapshot_current())
    assert json.loads(toolset.diff_profiles("balanced", "trailer-max"))["entries"]
    assert json.loads(toolset.apply_profile("balanced"))["dry_run"] is True
    assert json.loads(toolset.revert_last())["error"]["code"] == "nothing_to_revert"
    levels = json.dumps({"Medium": "balanced"})
    assert json.loads(toolset.export_scalability_ini(levels))["written"] is False
    assert fake.console.executed == []
