"""Persistent store for rented-server connection profiles."""
from __future__ import annotations

import logging
from pathlib import Path

from ..models.remote_profile import RemoteProfile
from ..utils.filesystem import ensure_dir
from ..utils.json_io import read_json, write_json

log = logging.getLogger(__name__)


class RemoteProfileStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._path = data_dir / "remote_profiles.json"
        self._profiles: dict[str, RemoteProfile] = {}
        self._load()

    def list_profiles(self) -> list[RemoteProfile]:
        return sorted(self._profiles.values(), key=lambda p: p.name.lower())

    def get_profile(self, profile_id: str) -> RemoteProfile | None:
        return self._profiles.get(profile_id)

    def upsert(self, profile: RemoteProfile) -> None:
        self._profiles[profile.profile_id] = profile
        self._save()

    def remove(self, profile_id: str) -> RemoteProfile | None:
        profile = self._profiles.pop(profile_id, None)
        if profile is not None:
            self._save()
        return profile

    def _load(self) -> None:
        data = read_json(self._path)
        for entry in data.get("profiles", []):
            try:
                profile = RemoteProfile.from_dict(entry)
                self._profiles[profile.profile_id] = profile
            except Exception as exc:
                log.warning("Skipping corrupt remote profile: %s", exc)

    def _save(self) -> None:
        ensure_dir(self.data_dir)
        write_json(self._path, {"profiles": [p.to_dict() for p in self.list_profiles()]})
