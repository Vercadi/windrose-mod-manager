"""Testable helpers for constructing tabs only when needed."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class LazyTabController:
    factories: dict[str, Callable[[], Any]]
    constructed: dict[str, Any] = field(default_factory=dict)

    def ensure(self, name: str) -> Any:
        if name in self.constructed:
            return self.constructed[name]
        if name not in self.factories:
            raise KeyError(name)
        instance = self.factories[name]()
        self.constructed[name] = instance
        return instance

    def is_constructed(self, name: str) -> bool:
        return name in self.constructed
