"""JSON read/write with error handling."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON file and return its contents as a dict."""
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except FileNotFoundError:
        log.warning("JSON file not found: %s", path)
        return {}
    except json.JSONDecodeError as exc:
        log.error("Invalid JSON in %s: %s", path, exc)
        return {}


def write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    """Write data to a JSON file atomically (write-then-rename)."""
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        log.info("Wrote JSON to %s", path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
