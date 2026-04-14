"""Name and path utilities."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import PurePosixPath


def sanitize_mod_id(name: str) -> str:
    """Turn a human-readable mod name into a safe filesystem-friendly id."""
    slug = re.sub(r"[^\w\-.]", "_", name.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug.lower() if slug else f"mod_{uuid.uuid4().hex[:8]}"


def timestamp_slug() -> str:
    """Return a compact timestamp suitable for file/folder names."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def mod_display_name_from_archive(archive_path: str) -> str:
    """Derive a human-friendly mod name from an archive filename."""
    name = PurePosixPath(archive_path).stem
    name = re.sub(r"[-_]+", " ", name)
    return name.title()
