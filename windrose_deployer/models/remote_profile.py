from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import uuid4


@dataclass
class RemoteProfile:
    """Saved connection settings for a rented server."""

    profile_id: str
    name: str
    host: str = ""
    port: int = 22
    username: str = ""
    auth_mode: str = "password"  # "password" | "key"
    password: str = ""
    private_key_path: str = ""
    remote_root_dir: str = ""
    remote_mods_dir: str = ""
    remote_server_description_path: str = ""
    remote_save_root: str = ""
    restart_command: str = ""

    @staticmethod
    def _normalize_remote_path(value: str) -> str:
        raw = (value or "").strip().replace("\\", "/")
        if not raw:
            return ""
        if raw == "/":
            return raw
        normalized = str(PurePosixPath(raw))
        if raw.startswith("/") and not normalized.startswith("/"):
            normalized = "/" + normalized
        return normalized

    def normalized_root_dir(self) -> str:
        return self._normalize_remote_path(self.remote_root_dir)

    def resolved_mods_dir(self) -> str:
        explicit = self._normalize_remote_path(self.remote_mods_dir)
        if explicit:
            return explicit
        root = self.normalized_root_dir()
        if not root:
            return ""
        return str(PurePosixPath(root).joinpath("R5", "Content", "Paks", "~mods"))

    def has_explicit_mods_dir(self) -> bool:
        return bool(self._normalize_remote_path(self.remote_mods_dir))

    def resolved_server_description_path(self) -> str:
        explicit = self._normalize_remote_path(self.remote_server_description_path)
        if explicit:
            return explicit
        root = self.normalized_root_dir()
        if not root:
            return ""
        return str(PurePosixPath(root).joinpath("R5", "ServerDescription.json"))

    def resolved_save_root(self) -> str:
        explicit = self._normalize_remote_path(self.remote_save_root)
        if explicit:
            return explicit
        root = self.normalized_root_dir()
        if not root:
            return ""
        return str(PurePosixPath(root).joinpath("R5", "Saved"))

    def apply_root_defaults(self, *, overwrite: bool = False) -> None:
        root = self.normalized_root_dir()
        self.remote_root_dir = root
        if not root:
            return
        if overwrite or not self._normalize_remote_path(self.remote_mods_dir):
            self.remote_mods_dir = self.resolved_mods_dir()
        if overwrite or not self._normalize_remote_path(self.remote_server_description_path):
            self.remote_server_description_path = self.resolved_server_description_path()
        if overwrite or not self._normalize_remote_path(self.remote_save_root):
            self.remote_save_root = self.resolved_save_root()

    @classmethod
    def new(cls, name: str = "New Remote Profile") -> "RemoteProfile":
        return cls(profile_id=uuid4().hex, name=name)

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "auth_mode": self.auth_mode,
            "password": self.password,
            "private_key_path": self.private_key_path,
            "remote_root_dir": self.remote_root_dir,
            "remote_mods_dir": self.remote_mods_dir,
            "remote_server_description_path": self.remote_server_description_path,
            "remote_save_root": self.remote_save_root,
            "restart_command": self.restart_command,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RemoteProfile":
        return cls(
            profile_id=data.get("profile_id", uuid4().hex),
            name=data.get("name", "Remote Profile"),
            host=data.get("host", ""),
            port=int(data.get("port", 22) or 22),
            username=data.get("username", ""),
            auth_mode=data.get("auth_mode", "password"),
            password=data.get("password", ""),
            private_key_path=data.get("private_key_path", ""),
            remote_root_dir=data.get("remote_root_dir", ""),
            remote_mods_dir=data.get("remote_mods_dir", ""),
            remote_server_description_path=data.get("remote_server_description_path", ""),
            remote_save_root=data.get("remote_save_root", ""),
            restart_command=data.get("restart_command", ""),
        )
