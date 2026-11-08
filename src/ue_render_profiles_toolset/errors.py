"""Typed error of the library."""

from __future__ import annotations

MAX_MESSAGE_CHARS = 200

CODE_EXTENDS_CYCLE = "extends_cycle"
CODE_UNKNOWN_PROFILE = "unknown_profile"
CODE_INVALID_PROFILE = "invalid_profile"
CODE_NOTHING_TO_REVERT = "nothing_to_revert"


def clip(text: str, limit: int = MAX_MESSAGE_CHARS) -> str:
    """Return ``text`` shortened to at most ``limit`` characters."""
    if len(text) <= limit:
        return text
    cut = max(limit - 3, 0)
    return text[:cut] + "..."


class ProfileError(Exception):
    """Base error of the library.

    Attributes:
        code: Stable machine-readable code: ``extends_cycle``, ``unknown_profile``,
            ``invalid_profile`` or ``nothing_to_revert``.
        message: Human-readable text, never longer than 200 characters.
    """

    def __init__(self, code: str, message: str) -> None:
        clipped = clip(message)
        super().__init__(f"{code}: {clipped}")
        self.code = code
        self.message = clipped
