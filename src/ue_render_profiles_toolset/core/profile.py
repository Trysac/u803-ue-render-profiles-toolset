"""Profile model, parsing and ``extends`` resolution (pure, no Unreal imports)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ue_render_profiles_toolset.errors import (
    CODE_EXTENDS_CYCLE,
    CODE_INVALID_PROFILE,
    CODE_UNKNOWN_PROFILE,
    ProfileError,
    clip,
)

Number = int | float

MAX_NAME_LENGTH = 64
MAX_CVARS = 256
MAX_EXTENDS_DEPTH = 16
MAX_NOTE_LENGTH = 500
MAX_HARDWARE_LENGTH = 200
MAX_JSON_BYTES = 1_048_576
MAX_ABS_VALUE = 1e12

_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_CVAR_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.]{0,127}")
_ALLOWED_KEYS = frozenset({"name", "extends", "note", "target_hardware", "cvars"})


@dataclass(frozen=True)
class Profile:
    """A named, optionally inheriting set of CVar values."""

    name: str
    extends: str | None = None
    note: str = ""
    target_hardware: str = ""
    cvars: Mapping[str, Number] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cvars", MappingProxyType(dict(self.cvars)))


def _fail(message: str) -> ProfileError:
    return ProfileError(CODE_INVALID_PROFILE, message)


def is_number(value: object) -> bool:
    """Return True for finite, bounded ints and floats (booleans are rejected)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return abs(value) <= MAX_ABS_VALUE


def is_cvar_name(value: object) -> bool:
    """Return True when ``value`` is a syntactically valid CVar name."""
    return isinstance(value, str) and _CVAR_RE.fullmatch(value) is not None


def _check_name(value: object, what: str) -> str:
    if not isinstance(value, str) or _NAME_RE.fullmatch(value) is None:
        raise _fail(f"invalid profile {what}")
    return value


def _check_text(value: object, what: str, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise _fail(f"{what} must be a string of at most {limit} characters")
    return value


def load_json(text: str, what: str) -> object:
    """Parse JSON text with a size limit, raising ``ProfileError`` on any failure."""
    if len(text.encode("utf-8")) > MAX_JSON_BYTES:
        raise _fail(f"{what} is larger than {MAX_JSON_BYTES} bytes")
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        raise _fail(f"{what} is not valid JSON") from None


def profile_from_dict(data: object) -> Profile:
    """Build a ``Profile`` from decoded JSON, enforcing structure and size limits."""
    if not isinstance(data, dict):
        raise _fail("profile must be a JSON object")
    unknown = sorted(str(key) for key in data if key not in _ALLOWED_KEYS)
    if unknown:
        names = ", ".join(clip(key, 40) for key in unknown[:5])
        raise _fail(f"unknown profile keys: {names}")
    name = _check_name(data.get("name"), "name")
    raw_extends = data.get("extends")
    extends = None if raw_extends is None else _check_name(raw_extends, "extends")
    note = _check_text(data.get("note", ""), "note", MAX_NOTE_LENGTH)
    hardware = _check_text(
        data.get("target_hardware", ""),
        "target_hardware",
        MAX_HARDWARE_LENGTH,
    )
    raw_cvars = data.get("cvars", {})
    if not isinstance(raw_cvars, dict):
        raise _fail("cvars must be a JSON object")
    if len(raw_cvars) > MAX_CVARS:
        raise _fail(f"a profile may set at most {MAX_CVARS} cvars")
    cvars: dict[str, Number] = {}
    for key, value in raw_cvars.items():
        if not is_cvar_name(key):
            raise _fail(f"invalid cvar name: {clip(str(key), 60)}")
        if not is_number(value):
            raise _fail(f"cvar value must be a finite number: {clip(key, 60)}")
        cvars[key] = value
    return Profile(
        name=name,
        extends=extends,
        note=note,
        target_hardware=hardware,
        cvars=cvars,
    )


def profile_from_json(text: str) -> Profile:
    """Parse a profile from JSON text."""
    return profile_from_dict(load_json(text, "profile"))


def merge_cvars(*levels: Mapping[str, Number]) -> dict[str, Number]:
    """Merge CVar levels key by key; later levels override earlier ones."""
    merged: dict[str, Number] = {}
    for level in levels:
        merged.update(level)
    return merged


def resolve_chain(name: str, profiles: Mapping[str, Profile]) -> tuple[Profile, ...]:
    """Return the profiles from ``name`` up to its root ancestor (leaf first).

    Raises:
        ProfileError: ``extends_cycle``, ``unknown_profile`` or ``invalid_profile`` (too deep).
    """
    chain: list[Profile] = []
    seen: list[str] = []
    current: str | None = name
    while current is not None:
        if current in seen:
            start = seen.index(current)
            cycle = [*seen[start:], current]
            names = " -> ".join(clip(item, 40) for item in cycle)
            raise ProfileError(CODE_EXTENDS_CYCLE, f"extends cycle: {names}")
        if len(seen) >= MAX_EXTENDS_DEPTH:
            raise _fail(f"extends chain is deeper than {MAX_EXTENDS_DEPTH}")
        profile = profiles.get(current)
        if profile is None:
            raise ProfileError(CODE_UNKNOWN_PROFILE, f"unknown profile: {clip(current, 64)}")
        seen.append(current)
        chain.append(profile)
        current = profile.extends
    return tuple(chain)


def resolve_profile(name: str, profiles: Mapping[str, Profile]) -> Profile:
    """Resolve ``name`` by merging its ``extends`` chain; child values override parents."""
    chain = resolve_chain(name, profiles)
    leaf = chain[0]
    cvars = merge_cvars(*(item.cvars for item in reversed(chain)))
    note = next((item.note for item in chain if item.note), "")
    hardware = next((item.target_hardware for item in chain if item.target_hardware), "")
    return Profile(
        name=name,
        extends=leaf.extends,
        note=note,
        target_hardware=hardware,
        cvars=cvars,
    )
