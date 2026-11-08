"""The CVar catalog (whitelist) and the packaged example profiles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from types import MappingProxyType

from ue_render_profiles_toolset.core.profile import (
    Profile,
    is_cvar_name,
    is_number,
    load_json,
    profile_from_json,
)
from ue_render_profiles_toolset.errors import CODE_INVALID_PROFILE, ProfileError, clip

NOT_DOCUMENTED = "not documented"
DOCS_PREFIX = "https://dev.epicgames.com/documentation/"
MAX_CATALOG_ENTRIES = 512
MAX_PROFILES = 64

_PACKAGE = "ue_render_profiles_toolset"
_ENTRY_KEYS = frozenset(
    {
        "name",
        "type",
        "range",
        "description",
        "impact",
        "source",
        "warnings",
        "requires_restart",
        "scalability_group",
    }
)


@dataclass(frozen=True)
class CVarSpec:
    """One catalog entry. ``minimum``/``maximum`` are None when the range is not documented."""

    name: str
    type: str
    minimum: float | None
    maximum: float | None
    description: str
    impact: str
    source: str
    warnings: tuple[str, ...]
    requires_restart: bool
    scalability_group: str | None

    @property
    def range_text(self) -> str:
        """Return the documented range as text, or 'not documented'."""
        if self.minimum is None or self.maximum is None:
            return NOT_DOCUMENTED
        return f"{self.minimum:g}..{self.maximum:g}"


@dataclass(frozen=True)
class Catalog:
    """Immutable mapping of CVar name to ``CVarSpec``; its keys are the command whitelist."""

    cvars: Mapping[str, CVarSpec]

    def __post_init__(self) -> None:
        object.__setattr__(self, "cvars", MappingProxyType(dict(self.cvars)))

    def get(self, name: str) -> CVarSpec | None:
        """Return the spec for ``name`` or None."""
        return self.cvars.get(name)

    def __contains__(self, name: object) -> bool:
        return name in self.cvars

    @property
    def whitelist(self) -> frozenset[str]:
        """Names of the CVars that commands may name."""
        return frozenset(self.cvars)


def _fail(message: str) -> ProfileError:
    return ProfileError(CODE_INVALID_PROFILE, f"catalog: {message}")


def _text(raw: dict[str, object], key: str, name: str) -> str:
    value = raw[key]
    if not isinstance(value, str) or not value:
        raise _fail(f"{key} of {clip(name, 60)} must be a non-empty string")
    return value


def _parse_range(raw: object, name: str) -> tuple[float | None, float | None]:
    if raw == NOT_DOCUMENTED:
        return None, None
    if not isinstance(raw, dict) or set(raw) != {"min", "max"}:
        raise _fail(f"range of {clip(name, 60)} must be 'not documented' or {{min, max}}")
    low, high = raw["min"], raw["max"]
    if not is_number(low) or not is_number(high) or low > high:
        raise _fail(f"range of {clip(name, 60)} is invalid")
    return float(low), float(high)


def _parse_spec(raw: object) -> CVarSpec:
    if not isinstance(raw, dict) or set(raw) != _ENTRY_KEYS:
        raise _fail("entry must be an object with exactly the documented keys")
    name = raw["name"]
    if not is_cvar_name(name):
        raise _fail(f"invalid cvar name: {clip(str(name), 60)}")
    kind = raw["type"]
    if kind not in ("int", "float"):
        raise _fail(f"type of {clip(name, 60)} must be 'int' or 'float'")
    minimum, maximum = _parse_range(raw["range"], name)
    source = _text(raw, "source", name)
    if not source.startswith(DOCS_PREFIX):
        raise _fail(f"source of {clip(name, 60)} must be official Unreal documentation")
    warnings = raw["warnings"]
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        raise _fail(f"warnings of {clip(name, 60)} must be a list of strings")
    restart = raw["requires_restart"]
    if not isinstance(restart, bool):
        raise _fail(f"requires_restart of {clip(name, 60)} must be a boolean")
    group = raw["scalability_group"]
    if group is not None and not (isinstance(group, str) and group):
        raise _fail(f"scalability_group of {clip(name, 60)} must be null or a string")
    return CVarSpec(
        name=name,
        type=kind,
        minimum=minimum,
        maximum=maximum,
        description=_text(raw, "description", name),
        impact=_text(raw, "impact", name),
        source=source,
        warnings=tuple(warnings),
        requires_restart=restart,
        scalability_group=group,
    )


def parse_catalog(data: object) -> Catalog:
    """Validate decoded catalog JSON and build a ``Catalog``."""
    if not isinstance(data, dict) or data.get("version") != 1:
        raise _fail("expected an object with version 1")
    entries = data.get("cvars")
    if not isinstance(entries, list):
        raise _fail("cvars must be a list")
    if len(entries) > MAX_CATALOG_ENTRIES:
        raise _fail(f"at most {MAX_CATALOG_ENTRIES} entries are allowed")
    specs: dict[str, CVarSpec] = {}
    for raw in entries:
        spec = _parse_spec(raw)
        if spec.name in specs:
            raise _fail(f"duplicate cvar: {clip(spec.name, 60)}")
        specs[spec.name] = spec
    return Catalog(cvars=specs)


def _read_resource(*parts: str) -> str:
    node = resources.files(_PACKAGE)
    for part in parts:
        node = node.joinpath(part)
    return node.read_bytes().decode("utf-8")


@lru_cache(maxsize=1)
def load_catalog() -> Catalog:
    """Load the packaged catalog (cached; the result is immutable)."""
    text = _read_resource("data", "catalog", "cvars.json")
    return parse_catalog(load_json(text, "catalog"))


def profiles_from_texts(texts: Mapping[str, str]) -> dict[str, Profile]:
    """Parse profiles from ``{file name: JSON text}``; each file must be ``<name>.json``."""
    if len(texts) > MAX_PROFILES:
        raise _fail(f"at most {MAX_PROFILES} profiles are allowed")
    result: dict[str, Profile] = {}
    for file_name in sorted(texts):
        profile = profile_from_json(texts[file_name])
        if file_name != f"{profile.name}.json":
            raise _fail(f"file name does not match profile name: {clip(file_name, 60)}")
        result[profile.name] = profile
    return result


def load_profiles() -> dict[str, Profile]:
    """Load the packaged example profiles."""
    folder = resources.files(_PACKAGE).joinpath("data").joinpath("profiles")
    names = sorted(entry.name for entry in folder.iterdir() if entry.name.endswith(".json"))
    texts = {name: _read_resource("data", "profiles", name) for name in names}
    return profiles_from_texts(texts)
