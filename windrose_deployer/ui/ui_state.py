"""Small UI state helpers shared by top-level screens."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BannerState:
    kind: str
    message: str
    background: str
    foreground: str = "#ecf0f1"


_BANNER_COLORS = {
    "info": "#1f4e79",
    "success": "#1f6f43",
    "warning": "#7d5a18",
    "error": "#7f2a24",
}


def banner(kind: str, message: str) -> BannerState:
    normalized = kind if kind in _BANNER_COLORS else "info"
    return BannerState(
        kind=normalized,
        message=str(message or "").strip(),
        background=_BANNER_COLORS[normalized],
    )
