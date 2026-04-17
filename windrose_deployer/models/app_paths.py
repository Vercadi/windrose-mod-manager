from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AppPaths:
    """All resolved filesystem paths the application needs."""

    client_root: Optional[Path] = None
    server_root: Optional[Path] = None
    dedicated_server_root: Optional[Path] = None
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
    def bundled_server_description_json(self) -> Optional[Path]:
        if self.server_root:
            return self.server_root / "R5" / "ServerDescription.json"
        return None

    @property
    def bundled_server_save_root(self) -> Optional[Path]:
        if self.server_root:
            return self.server_root / "R5" / "Saved"
        return None

    @property
    def dedicated_server_paks(self) -> Optional[Path]:
        if self.dedicated_server_root:
            return self.dedicated_server_root / "R5" / "Content" / "Paks"
        return None

    @property
    def dedicated_server_mods(self) -> Optional[Path]:
        if self.dedicated_server_paks:
            return self.dedicated_server_paks / "~mods"
        return None

    @property
    def dedicated_server_description_json(self) -> Optional[Path]:
        if self.dedicated_server_root:
            return self.dedicated_server_root / "R5" / "ServerDescription.json"
        return None

    @property
    def dedicated_server_save_root(self) -> Optional[Path]:
        if self.local_save_root:
            return self.local_save_root
        if self.dedicated_server_root:
            return self.dedicated_server_root / "R5" / "Saved"
        return None

    @property
    def effective_local_save_root(self) -> Optional[Path]:
        return self.dedicated_server_save_root or self.bundled_server_save_root

    @property
    def server_description_json(self) -> Optional[Path]:
        """Compatibility alias for the dedicated server config path."""
        return self.dedicated_server_description_json

    @property
    def local_save_profiles(self) -> Optional[Path]:
        root = self.effective_local_save_root
        if root:
            return root / "SaveProfiles"
        return None

    @property
    def local_save_games(self) -> Optional[Path]:
        root = self.effective_local_save_root
        if root:
            return root / "SaveGames"
        return None

    # --- serialisation ---------------------------------------------------- #

    def to_dict(self) -> dict:
        return {
            "client_root": str(self.client_root) if self.client_root else None,
            "server_root": str(self.server_root) if self.server_root else None,
            "dedicated_server_root": str(self.dedicated_server_root) if self.dedicated_server_root else None,
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
            dedicated_server_root=_p(d.get("dedicated_server_root")),
            local_config=_p(d.get("local_config")),
            local_save_root=_p(d.get("local_save_root")),
            backup_dir=_p(d.get("backup_dir")),
            data_dir=_p(d.get("data_dir")),
        )
