from __future__ import annotations

import logging
from pathlib import Path

from ..models.profile import Profile
from ..utils.filesystem import ensure_dir
from ..utils.json_io import read_json, write_json

log = logging.getLogger(__name__)


class ProfileStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._path = data_dir / "profiles.json"
        self._profiles: dict[str, Profile] = {}
        self._load()

    def list_profiles(self) -> list[Profile]:
        return sorted(self._profiles.values(), key=lambda item: item.name.lower())

    def get_profile(self, profile_id: str) -> Profile | None:
        return self._profiles.get(profile_id)

    def upsert(self, profile: Profile) -> None:
        self._profiles[profile.profile_id] = profile
        self._save()

    def remove(self, profile_id: str) -> Profile | None:
        profile = self._profiles.pop(profile_id, None)
        if profile is not None:
            self._save()
        return profile

    def _load(self) -> None:
        if not self._path.is_file():
            return
        data = read_json(self._path)
        for entry in data.get("profiles", []):
            try:
                profile = Profile.from_dict(entry)
                self._profiles[profile.profile_id] = profile
            except Exception as exc:
                log.warning("Skipping corrupt profile: %s", exc)

    def _save(self) -> None:
        ensure_dir(self.data_dir)
        write_json(self._path, {"profiles": [profile.to_dict() for profile in self.list_profiles()]})
