from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AppPaths:
    """All resolved filesystem paths the application needs."""

    client_root: Optional[Path] = None
    server_root: Optional[Path] = None
    local_config: Optional[Path] = None
    local_save_root: Optional[Path] = None
    backup_dir: Optional[Path] = None
    data_dir: Optional[Path] = None

    # --- derived helpers -------------------------------------------------- #

    @property
    def client_paks(self) -> Optional[Path]:
        if self.client_root:
            return self.client_root / "R5" / "Content" / "Paks"
        return None

    @property
    def client_mods(self) -> Optional[Path]:
        if self.client_paks:
            return self.client_paks / "~mods"
        return None

    @property
    def server_paks(self) -> Optional[Path]:
        if self.server_root:
            return self.server_root / "R5" / "Content" / "Paks"
        return None

    @property
    def server_mods(self) -> Optional[Path]:
        if self.server_paks:
            return self.server_paks / "~mods"
        return None

    @property
    def server_description_json(self) -> Optional[Path]:
        """ServerDescription.json lives at <client_root>/R5/, not inside the
        dedicated server folder."""
        if self.client_root:
            return self.client_root / "R5" / "ServerDescription.json"
        return None

    @property
    def local_save_profiles(self) -> Optional[Path]:
        if self.local_save_root:
            return self.local_save_root / "SaveProfiles"
        return None

    @property
    def local_save_games(self) -> Optional[Path]:
        if self.local_save_root:
            return self.local_save_root / "SaveGames"
        return None

    # --- serialisation ---------------------------------------------------- #

    def to_dict(self) -> dict:
        return {
            "client_root": str(self.client_root) if self.client_root else None,
            "server_root": str(self.server_root) if self.server_root else None,
            "local_config": str(self.local_config) if self.local_config else None,
            "local_save_root": str(self.local_save_root) if self.local_save_root else None,
            "backup_dir": str(self.backup_dir) if self.backup_dir else None,
            "data_dir": str(self.data_dir) if self.data_dir else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AppPaths:
        def _p(v: Optional[str]) -> Optional[Path]:
            return Path(v) if v else None

        return cls(
            client_root=_p(d.get("client_root")),
            server_root=_p(d.get("server_root")),
            local_config=_p(d.get("local_config")),
            local_save_root=_p(d.get("local_save_root")),
            backup_dir=_p(d.get("backup_dir")),
            data_dir=_p(d.get("data_dir")),
        )
