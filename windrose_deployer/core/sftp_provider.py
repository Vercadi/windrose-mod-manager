"""SFTP implementation for rented-server deployment."""
from __future__ import annotations

import os
import posixpath
import stat
from pathlib import Path

from ..models.remote_profile import RemoteProfile
from .remote_provider import RemoteEntry


class SftpProvider:
    def __init__(self, profile: RemoteProfile):
        self.profile = profile
        self._paramiko = self._import_paramiko()
        self._ssh = self._paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(self._paramiko.AutoAddPolicy())
        self._connect()
        self._sftp = self._ssh.open_sftp()

    @staticmethod
    def _import_paramiko():
        try:
            import paramiko
        except ImportError as exc:
            raise RuntimeError("paramiko is required for SFTP remote support.") from exc
        return paramiko

    def _connect(self) -> None:
        kwargs = {
            "hostname": self.profile.host,
            "port": self.profile.port,
            "username": self.profile.username,
            "timeout": 10,
            "banner_timeout": 10,
            "auth_timeout": 10,
            "look_for_keys": False,
            "allow_agent": False,
        }
        if self.profile.auth_mode == "key" and self.profile.private_key_path:
            key_path = self._resolve_private_key_path(self.profile.private_key_path)
            kwargs["key_filename"] = key_path
        else:
            kwargs["password"] = self.profile.password
        self._ssh.connect(**kwargs)

    @staticmethod
    def _resolve_private_key_path(raw_value: str) -> str:
        raw = (raw_value or "").strip()
        if not raw:
            raise ValueError("Private key path is required for key authentication.")
        if "\n" in raw or "\r" in raw:
            raise ValueError(
                "Private Key must be a file path, not pasted key contents."
            )
        expanded = os.path.expandvars(os.path.expanduser(raw))
        path = Path(expanded)
        if not path.is_file():
            raise FileNotFoundError(f"Private key file not found: {path}")
        return str(path)

    def close(self) -> None:
        try:
            self._sftp.close()
        except Exception:
            pass
        try:
            self._ssh.close()
        except Exception:
            pass

    def path_exists(self, remote_path: str) -> bool:
        try:
            self._sftp.stat(remote_path)
            return True
        except OSError:
            return False

    def list_files(self, remote_dir: str) -> list[str]:
        items: list[str] = []
        for entry in self._sftp.listdir_attr(remote_dir):
            items.append(posixpath.join(remote_dir.rstrip("/"), entry.filename))
        return sorted(items)

    def list_entries(self, remote_dir: str) -> list[RemoteEntry]:
        entries: list[RemoteEntry] = []
        for entry in self._sftp.listdir_attr(remote_dir):
            full_path = posixpath.join(remote_dir.rstrip("/"), entry.filename)
            entries.append(RemoteEntry(
                path=full_path,
                name=entry.filename,
                is_dir=stat.S_ISDIR(entry.st_mode),
            ))
        return sorted(entries, key=lambda item: item.name.lower())

    def ensure_dir(self, remote_dir: str) -> None:
        if not remote_dir:
            return
        current = ""
        for part in remote_dir.split("/"):
            if not part:
                continue
            current = f"{current}/{part}" if current else f"/{part}" if remote_dir.startswith("/") else part
            try:
                self._sftp.stat(current)
            except OSError:
                self._sftp.mkdir(current)

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        parent = posixpath.dirname(remote_path)
        if parent:
            self.ensure_dir(parent)
        with self._sftp.file(remote_path, "wb") as handle:
            handle.write(data)

    def read_bytes(self, remote_path: str) -> bytes:
        with self._sftp.file(remote_path, "rb") as handle:
            return handle.read()

    def execute(self, command: str) -> tuple[bool, str]:
        stdin, stdout, stderr = self._ssh.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        if exit_code == 0:
            return True, output
        return False, err or output
