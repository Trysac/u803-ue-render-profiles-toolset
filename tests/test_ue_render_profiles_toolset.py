"""Tests of the package surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.unreal import make_fake

import ue_render_profiles_toolset as pkg
from ue_render_profiles_toolset import ListProfilesResult, snapshot_current
from ue_render_profiles_toolset.results import to_dict


def test_version_and_exports() -> None:
    assert pkg.__version__ == "0.2.0"
    for name in pkg.__all__:
        assert hasattr(pkg, name)


def test_core_never_imports_unreal() -> None:
    core = Path(pkg.__file__).parent / "core"
    for source in core.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "import unreal" not in text
        assert "from unreal" not in text


def test_to_dict_converts_results_and_rejects_other_values() -> None:
    data = to_dict(snapshot_current(make_fake()))
    assert "summary" in data
    assert data["values"]["r.Fog"] == 1
    with pytest.raises(TypeError):
        to_dict(5)
    with pytest.raises(TypeError):
        to_dict(ListProfilesResult)
