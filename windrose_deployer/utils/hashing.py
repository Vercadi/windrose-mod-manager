"""File and data hashing helpers."""
from __future__ import annotations

import hashlib
from pathlib import Path


def hash_file(path: Path, algorithm: str = "sha256", chunk_size: int = 1 << 16) -> str:
    """Return hex digest of a file."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def hash_bytes(data: bytes, algorithm: str = "sha256") -> str:
    """Return hex digest of raw bytes."""
    return hashlib.new(algorithm, data).hexdigest()
