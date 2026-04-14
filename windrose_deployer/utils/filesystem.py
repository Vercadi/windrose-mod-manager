"""Safe filesystem helpers — never silently overwrite."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import logging

log = logging.getLogger(__name__)


def ensure_dir(path: Path) -> Path:
    """Create directory (and parents) if it doesn't exist. Returns the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_copy(src: Path, dest: Path, backup_dir: Optional[Path] = None) -> Optional[Path]:
    """Copy *src* to *dest*.

    If *dest* already exists and *backup_dir* is provided, the existing file is
    copied into *backup_dir* first and its backup path is returned.
    """
    backup_path: Optional[Path] = None

    if dest.exists() and backup_dir is not None:
        ensure_dir(backup_dir)
        backup_path = backup_dir / dest.name
        counter = 1
        while backup_path.exists():
            backup_path = backup_dir / f"{dest.stem}_{counter}{dest.suffix}"
            counter += 1
        shutil.copy2(dest, backup_path)
        log.info("Backed up existing %s -> %s", dest, backup_path)

    ensure_dir(dest.parent)
    shutil.copy2(src, dest)
    log.info("Copied %s -> %s", src, dest)
    return backup_path


def safe_move(src: Path, dest: Path) -> None:
    """Move a file, creating parent dirs as needed."""
    ensure_dir(dest.parent)
    shutil.move(str(src), str(dest))
    log.info("Moved %s -> %s", src, dest)


def safe_delete(path: Path) -> bool:
    """Delete a file if it exists. Returns True if deleted."""
    try:
        if path.is_file():
            path.unlink()
            log.info("Deleted %s", path)
            return True
        if path.is_dir():
            shutil.rmtree(path)
            log.info("Deleted directory %s", path)
            return True
    except OSError as exc:
        log.error("Failed to delete %s: %s", path, exc)
    return False
