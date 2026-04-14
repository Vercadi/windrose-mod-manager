"""Unified archive handler — abstracts zip, 7z, and rar behind one interface."""
from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".zip", ".7z", ".rar"}


@dataclass
class ArchiveEntryInfo:
    """Minimal info for a single entry inside an archive."""
    filename: str
    is_dir: bool
    file_size: int


@runtime_checkable
class ArchiveReader(Protocol):
    """Common interface every archive backend must support."""

    def list_entries(self) -> list[ArchiveEntryInfo]: ...
    def read_file(self, entry_path: str) -> bytes: ...
    def close(self) -> None: ...


# ------------------------------------------------------------------ zip

class ZipArchiveReader:
    def __init__(self, path: Path):
        self._zf = zipfile.ZipFile(path, "r")

    def list_entries(self) -> list[ArchiveEntryInfo]:
        return [
            ArchiveEntryInfo(
                filename=zi.filename,
                is_dir=zi.is_dir(),
                file_size=zi.file_size,
            )
            for zi in self._zf.infolist()
        ]

    def read_file(self, entry_path: str) -> bytes:
        return self._zf.read(entry_path)

    def close(self) -> None:
        self._zf.close()


# ------------------------------------------------------------------ 7z

class SevenZipArchiveReader:
    """py7zr only supports extracting to disk, so we extract everything to a
    temp directory once and read files from there."""

    def __init__(self, path: Path):
        import py7zr
        import tempfile
        self._path = path
        self._archive = py7zr.SevenZipFile(path, "r")
        self._entries: Optional[list[ArchiveEntryInfo]] = None
        self._tmpdir: Optional[Path] = None
        self._tmpdir_obj = None

    def list_entries(self) -> list[ArchiveEntryInfo]:
        if self._entries is None:
            self._entries = [
                ArchiveEntryInfo(
                    filename=entry.filename.replace("\\", "/"),
                    is_dir=entry.is_directory,
                    file_size=entry.uncompressed if hasattr(entry, "uncompressed") else 0,
                )
                for entry in self._archive.list()
            ]
        return self._entries

    def _ensure_extracted(self) -> None:
        if self._tmpdir is not None:
            return
        import tempfile
        self._tmpdir_obj = tempfile.TemporaryDirectory(prefix="wmd_7z_")
        self._tmpdir = Path(self._tmpdir_obj.name)
        self._archive.extractall(path=str(self._tmpdir))
        log.info("Extracted 7z to temp: %s", self._tmpdir)

    def read_file(self, entry_path: str) -> bytes:
        self._ensure_extracted()
        # Try the path as-is, then with backslash variant
        for candidate in (entry_path, entry_path.replace("/", "\\")):
            full = self._tmpdir / candidate
            if full.is_file():
                return full.read_bytes()
        raise KeyError(f"Entry not found in extracted 7z: {entry_path}")

    def close(self) -> None:
        try:
            self._archive.close()
        except Exception:
            pass
        if self._tmpdir_obj:
            try:
                self._tmpdir_obj.cleanup()
            except Exception:
                pass
            self._tmpdir_obj = None
            self._tmpdir = None


# ------------------------------------------------------------------ rar

class RarArchiveReader:
    def __init__(self, path: Path):
        import rarfile
        self._rf = rarfile.RarFile(str(path), "r")

    def list_entries(self) -> list[ArchiveEntryInfo]:
        return [
            ArchiveEntryInfo(
                filename=ri.filename.replace("\\", "/"),
                is_dir=ri.is_dir(),
                file_size=ri.file_size,
            )
            for ri in self._rf.infolist()
        ]

    def read_file(self, entry_path: str) -> bytes:
        return self._rf.read(entry_path)

    def close(self) -> None:
        self._rf.close()


# ------------------------------------------------------------------ factory

def open_archive(path: Path) -> ArchiveReader:
    """Open an archive file and return the appropriate reader."""
    suffix = path.suffix.lower()

    if suffix == ".zip":
        return ZipArchiveReader(path)
    elif suffix == ".7z":
        return SevenZipArchiveReader(path)
    elif suffix == ".rar":
        return RarArchiveReader(path)
    else:
        raise ValueError(f"Unsupported archive format: {suffix}")


def is_supported_archive(path: Path) -> bool:
    """Check if a file has a supported archive extension."""
    return path.suffix.lower() in SUPPORTED_EXTENSIONS
