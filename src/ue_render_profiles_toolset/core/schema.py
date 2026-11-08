"""Validation of profiles against the CVar catalog (stdlib only)."""

from __future__ import annotations

from dataclasses import dataclass

from ue_render_profiles_toolset.core.catalog import Catalog
from ue_render_profiles_toolset.core.profile import MAX_CVARS, Profile, is_number
from ue_render_profiles_toolset.errors import CODE_INVALID_PROFILE, ProfileError, clip

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    """One finding. Codes: unknown_cvar, invalid_type, out_of_range, too_many_cvars,
    restart_required (a warning)."""

    code: str
    cvar: str
    message: str
    severity: str


def _error(code: str, cvar: str, message: str) -> ValidationIssue:
    return ValidationIssue(code, clip(cvar, 128), message, SEVERITY_ERROR)


def validate_profile(profile: Profile, catalog: Catalog) -> tuple[ValidationIssue, ...]:
    """Report every problem of ``profile`` against ``catalog``; never fails silently."""
    if len(profile.cvars) > MAX_CVARS:
        return (_error("too_many_cvars", "", f"more than {MAX_CVARS} cvars"),)
    issues: list[ValidationIssue] = []
    for name in sorted(profile.cvars):
        value = profile.cvars[name]
        spec = catalog.get(name)
        if spec is None:
            issues.append(_error("unknown_cvar", name, "cvar is not in the catalog"))
            continue
        if not is_number(value):
            issues.append(_error("invalid_type", name, "value must be a finite number"))
            continue
        if spec.type == "int" and not isinstance(value, int):
            issues.append(_error("invalid_type", name, "value must be an integer"))
            continue
        if (
            spec.minimum is not None
            and spec.maximum is not None
            and (value < spec.minimum or value > spec.maximum)
        ):
            text = f"{value} is outside {spec.range_text}"
            issues.append(_error("out_of_range", name, text))
        if spec.requires_restart:
            issues.append(
                ValidationIssue(
                    "restart_required",
                    name,
                    "read-only or startup cvar: set it in config and restart",
                    SEVERITY_WARNING,
                )
            )
    return tuple(issues)


def has_errors(issues: tuple[ValidationIssue, ...]) -> bool:
    """Return True when any issue has error severity."""
    return any(issue.severity == SEVERITY_ERROR for issue in issues)


def ensure_valid(profile: Profile, catalog: Catalog) -> None:
    """Raise ``ProfileError`` (``invalid_profile``) when the profile has error issues."""
    errors = [i for i in validate_profile(profile, catalog) if i.severity == SEVERITY_ERROR]
    if errors:
        found = "; ".join(f"{i.code} {clip(i.cvar, 40)}" for i in errors[:5])
        raise ProfileError(
            CODE_INVALID_PROFILE,
            f"profile {clip(profile.name, 40)} is invalid: {found}",
        )
