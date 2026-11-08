"""A fake ``unreal`` surface backed by a CVar table (no Unreal needed)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ue_render_profiles_toolset.core.catalog import load_catalog

DEFAULT_READ_ONLY = frozenset({"r.Shadow.Virtual.Enable"})
WORLD = "fake-world"


def _parse(text: str) -> int | float:
    try:
        return int(text)
    except ValueError:
        return float(text)


class FakeConsole:
    """CVar table that records reads, executed commands and ignored writes."""

    def __init__(
        self,
        values: Mapping[str, Any],
        read_only: Iterable[str],
        forced: Mapping[str, Any],
        group_effects: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.group_effects = {k: dict(v) for k, v in (group_effects or {}).items()}
        self.values: dict[str, Any] = dict(values)
        self.read_only = set(read_only)
        self.forced = dict(forced)
        self.executed: list[str] = []
        self.reads: list[str] = []
        self.ignored: list[str] = []

    def read(self, name: str) -> Any:
        self.reads.append(name)
        if name not in self.values:
            raise KeyError(name)
        return self.values[name]

    def execute(self, command: str) -> None:
        self.executed.append(command)
        name, _, text = command.partition(" ")
        if name not in self.values:
            raise ValueError(f"unknown console variable: {name}")
        if name in self.read_only:
            self.ignored.append(name)
            return
        if name in self.forced:
            self.values[name] = self.forced[name]
            return
        self.values[name] = _parse(text)
        # An sg.* write re-applies its group: other CVars change as a side effect.
        self.values.update(self.group_effects.get(name, {}))


class _FakeSystemLibrary:
    def __init__(self, console: FakeConsole) -> None:
        self._console = console

    def get_console_variable_int_value(self, name: str) -> int:
        return int(self._console.read(name))

    def get_console_variable_float_value(self, name: str) -> float:
        return float(self._console.read(name))

    def execute_console_command(
        self,
        world_context_object: Any,
        command: str,
        specific_player: Any = None,
    ) -> None:
        if world_context_object != WORLD:
            raise ValueError("a world context object is required")
        self._console.execute(command)


class _FakeEditorSubsystem:
    def get_editor_world(self) -> str:
        return WORLD


class _FakePaths:
    def __init__(self, config_dir: str | None) -> None:
        self._config_dir = config_dir

    def project_config_dir(self) -> str:
        if self._config_dir is None:
            raise RuntimeError("no project config dir configured")
        return self._config_dir


class FakeUnreal:
    """Stands in for the ``unreal`` module."""

    def __init__(self, console: FakeConsole, config_dir: str | None) -> None:
        self.console = console
        self.SystemLibrary = _FakeSystemLibrary(console)
        self.UnrealEditorSubsystem = _FakeEditorSubsystem
        self.Paths = _FakePaths(config_dir)

    def get_editor_subsystem(self, subsystem_class: Any) -> Any:
        return subsystem_class()


def make_fake(
    values: Mapping[str, Any] | None = None,
    read_only: Iterable[str] | None = None,
    forced: Mapping[str, Any] | None = None,
    config_dir: str | None = None,
    group_effects: Mapping[str, Mapping[str, Any]] | None = None,
) -> FakeUnreal:
    """Build a fake with one entry per catalog CVar (ints 1, floats 100.0 unless overridden)."""
    table: dict[str, Any] = {}
    for name, spec in load_catalog().cvars.items():
        table[name] = 1 if spec.type == "int" else 100.0
    table.update(values or {})
    only = DEFAULT_READ_ONLY if read_only is None else read_only
    console = FakeConsole(table, only, forced or {}, group_effects)
    return FakeUnreal(console, config_dir)
