from __future__ import annotations

from dataclasses import dataclass

UI_SIZE_VALUES = ("compact", "default", "large")
CONFIRMATION_MODE_VALUES = ("always", "destructive_only", "reduced", "none")


@dataclass
class AppPreferences:
    """User-facing app behavior and readability preferences."""

    ui_size: str = "default"
    confirmation_mode: str = "destructive_only"
    show_welcome: bool = True

    def normalized(self) -> AppPreferences:
        ui_size = self.ui_size if self.ui_size in UI_SIZE_VALUES else "default"
        confirmation_mode = (
            self.confirmation_mode
            if self.confirmation_mode in CONFIRMATION_MODE_VALUES
            else "destructive_only"
        )
        return AppPreferences(
            ui_size=ui_size,
            confirmation_mode=confirmation_mode,
            show_welcome=bool(self.show_welcome),
        )

    def to_dict(self) -> dict:
        normalized = self.normalized()
        return {
            "ui_size": normalized.ui_size,
            "confirmation_mode": normalized.confirmation_mode,
            "show_welcome": bool(self.show_welcome),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> AppPreferences:
        if not isinstance(data, dict):
            return cls()
        return cls(
            ui_size=str(data.get("ui_size") or "default"),
            confirmation_mode=str(data.get("confirmation_mode") or "destructive_only"),
            show_welcome=bool(data.get("show_welcome", True)),
        ).normalized()
