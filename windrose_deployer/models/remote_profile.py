from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlsplit
from uuid import uuid4

SUPPORTED_REMOTE_PROTOCOLS = ("sftp", "ftp")


def normalize_remote_protocol(value: str) -> str:
    normalized = (value or "sftp").strip().lower()
    return normalized if normalized in SUPPORTED_REMOTE_PROTOCOLS else "sftp"


def default_port_for_protocol(protocol: str) -> int:
    return 21 if normalize_remote_protocol(protocol) == "ftp" else 22


def normalize_remote_endpoint(
    host: str,
    port: int | str | None,
    *,
    protocol: str = "sftp",
) -> tuple[str, int, str]:
    effective_protocol = normalize_remote_protocol(protocol)
    raw_host = (host or "").strip()
    explicit_protocol = ""
    explicit_port: int | None = None

    if "://" in raw_host:
        parsed = urlsplit(raw_host)
        explicit_protocol = normalize_remote_protocol(parsed.scheme)
        if parsed.path not in ("", "/"):
            raise ValueError("Host / IP should not include a path.")
        raw_host = parsed.hostname or ""
        explicit_port = parsed.port
    elif raw_host.count(":") == 1 and raw_host.rsplit(":", 1)[1].isdigit():
        host_part, port_part = raw_host.rsplit(":", 1)
        raw_host = host_part
        explicit_port = int(port_part)

    normalized_host = raw_host.strip().strip("[]")
    chosen_protocol = explicit_protocol or effective_protocol

    if explicit_port is not None:
        chosen_port = explicit_port
    elif port in (None, ""):
        chosen_port = default_port_for_protocol(chosen_protocol)
    else:
        chosen_port = int(str(port).strip())

    return normalized_host, chosen_port, chosen_protocol


@dataclass
class RemoteProfile:
    """Saved connection settings for a rented server."""

    profile_id: str
    name: str
    protocol: str = "sftp"
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

    def supports_key_auth(self) -> bool:
        return normalize_remote_protocol(self.protocol) == "sftp"

    def supports_remote_execute(self) -> bool:
        return normalize_remote_protocol(self.protocol) == "sftp"

    def normalized_for_connection(self) -> "RemoteProfile":
        """Return a trimmed, protocol-aware copy used for tests and saves."""
        host, port, resolved_protocol = normalize_remote_endpoint(
            self.host,
            self.port,
            protocol=self.protocol,
        )
        return RemoteProfile(
            profile_id=self.profile_id,
            name=(self.name or "Remote Profile").strip() or "Remote Profile",
            protocol=resolved_protocol,
            host=host,
            port=port,
            username=(self.username or "").strip(),
            auth_mode=(self.auth_mode or "password").strip() if resolved_protocol == "sftp" else "password",
            password=self.password,
            private_key_path=(self.private_key_path or "").strip() if resolved_protocol == "sftp" else "",
            remote_root_dir=self._normalize_remote_path(self.remote_root_dir),
            remote_mods_dir=self._normalize_remote_path(self.remote_mods_dir),
            remote_server_description_path=self._normalize_remote_path(self.remote_server_description_path),
            remote_save_root=self._normalize_remote_path(self.remote_save_root),
            restart_command=(self.restart_command or "").strip() if resolved_protocol == "sftp" else "",
        )

    def to_dict(self) -> dict:
        normalized = self.normalized_for_connection()
        protocol = normalize_remote_protocol(normalized.protocol)
        return {
            "profile_id": normalized.profile_id,
            "name": normalized.name,
            "protocol": protocol,
            "host": normalized.host,
            "port": normalized.port,
            "username": normalized.username,
            "auth_mode": normalized.auth_mode if protocol == "sftp" else "password",
            "password": normalized.password,
            "private_key_path": normalized.private_key_path if protocol == "sftp" else "",
            "remote_root_dir": normalized.remote_root_dir,
            "remote_mods_dir": normalized.remote_mods_dir,
            "remote_server_description_path": normalized.remote_server_description_path,
            "remote_save_root": normalized.remote_save_root,
            "restart_command": normalized.restart_command if protocol == "sftp" else "",
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RemoteProfile":
        protocol = normalize_remote_protocol(data.get("protocol", "sftp"))
        host, port, resolved_protocol = normalize_remote_endpoint(
            data.get("host", ""),
            data.get("port"),
            protocol=protocol,
        )
        return cls(
            profile_id=data.get("profile_id", uuid4().hex),
            name=data.get("name", "Remote Profile"),
            protocol=resolved_protocol,
            host=host,
            port=port,
            username=data.get("username", ""),
            auth_mode=data.get("auth_mode", "password") if resolved_protocol == "sftp" else "password",
            password=data.get("password", ""),
            private_key_path=data.get("private_key_path", "") if resolved_protocol == "sftp" else "",
            remote_root_dir=data.get("remote_root_dir", ""),
            remote_mods_dir=data.get("remote_mods_dir", ""),
            remote_server_description_path=data.get("remote_server_description_path", ""),
            remote_save_root=data.get("remote_save_root", ""),
            restart_command=data.get("restart_command", "") if resolved_protocol == "sftp" else "",
        )
