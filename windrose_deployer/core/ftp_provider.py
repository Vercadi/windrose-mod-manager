"""FTP implementation for hosted-server file access."""
from __future__ import annotations

import io
import posixpath
from ftplib import FTP, all_errors, error_perm

from ..models.remote_profile import RemoteProfile
from .remote_provider import RemoteEntry


class FtpProvider:
    def __init__(self, profile: RemoteProfile):
        self.profile = profile
        self._ftp = FTP()
        self._ftp.encoding = "utf-8"
        self._ftp.connect(profile.host, profile.port, timeout=15)
        self._ftp.login(profile.username, profile.password)

    def close(self) -> None:
        try:
            self._ftp.quit()
        except Exception:
            try:
                self._ftp.close()
            except Exception:
                pass

    def path_exists(self, remote_path: str) -> bool:
        normalized = self._normalize_path(remote_path)
        if normalized in {"", "/"}:
            return True
        current = self._safe_pwd()
        try:
            self._ftp.cwd(normalized)
            return True
        except all_errors:
            pass
        finally:
            if current is not None:
                self._safe_cwd(current)
        try:
            return self._ftp.size(normalized) is not None
        except all_errors:
            return self._path_is_listed(normalized)

    def list_files(self, remote_dir: str) -> list[str]:
        return [entry.path for entry in self.list_entries(remote_dir)]

    def list_entries(self, remote_dir: str) -> list[RemoteEntry]:
        normalized = self._normalize_path(remote_dir)
        try:
            return self._list_entries_mlsd(normalized)
        except all_errors:
            return self._list_entries_fallback(normalized)

    def ensure_dir(self, remote_dir: str) -> None:
        normalized = self._normalize_path(remote_dir)
        if not normalized or normalized == "/":
            return
        current = ""
        for part in [segment for segment in normalized.split("/") if segment]:
            current = f"{current}/{part}" if current else f"/{part}" if normalized.startswith("/") else part
            if self.path_exists(current):
                continue
            self._ftp.mkd(current)

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        normalized = self._normalize_path(remote_path)
        parent = posixpath.dirname(normalized)
        if parent:
            self.ensure_dir(parent)
        self._ftp.storbinary(f"STOR {normalized}", io.BytesIO(data))

    def delete_file(self, remote_path: str) -> None:
        self._ftp.delete(self._normalize_path(remote_path))

    def read_bytes(self, remote_path: str) -> bytes:
        data = bytearray()
        self._ftp.retrbinary(
            f"RETR {self._normalize_path(remote_path)}",
            data.extend,
        )
        return bytes(data)

    def execute(self, command: str) -> tuple[bool, str]:
        return False, "FTP profiles support file access only. Restart commands require SFTP/SSH."

    def _list_entries_mlsd(self, remote_dir: str) -> list[RemoteEntry]:
        entries: list[RemoteEntry] = []
        for name, facts in self._ftp.mlsd(remote_dir):
            if name in {".", ".."}:
                continue
            path = posixpath.join(remote_dir.rstrip("/") or "/", name)
            entries.append(
                RemoteEntry(
                    path=path,
                    name=name,
                    is_dir=facts.get("type") == "dir",
                )
            )
        return sorted(entries, key=lambda item: item.name.lower())

    def _list_entries_fallback(self, remote_dir: str) -> list[RemoteEntry]:
        names = self._ftp.nlst(remote_dir)
        entries: list[RemoteEntry] = []
        for item in names:
            path = self._normalize_path(item)
            name = posixpath.basename(path)
            if not name or name in {".", ".."}:
                continue
            entries.append(
                RemoteEntry(
                    path=path,
                    name=name,
                    is_dir=self._path_is_dir(path),
                )
            )
        deduped: dict[str, RemoteEntry] = {entry.path: entry for entry in entries}
        return sorted(deduped.values(), key=lambda entry: entry.name.lower())

    def _path_is_dir(self, remote_path: str) -> bool:
        current = self._safe_pwd()
        try:
            self._ftp.cwd(remote_path)
            return True
        except all_errors:
            return False
        finally:
            if current is not None:
                self._safe_cwd(current)

    def _path_is_listed(self, remote_path: str) -> bool:
        candidates = [remote_path]
        if remote_path and not remote_path.startswith("/"):
            candidates.append("/" + remote_path)

        for candidate in candidates:
            parent = posixpath.dirname(candidate)
            name = posixpath.basename(candidate)
            if not name:
                continue
            try:
                if any(entry.name == name for entry in self.list_entries(parent or ".")):
                    return True
            except all_errors:
                continue
        return False

    def _safe_pwd(self) -> str | None:
        try:
            return self._ftp.pwd()
        except all_errors:
            return None

    def _safe_cwd(self, remote_dir: str) -> None:
        try:
            self._ftp.cwd(remote_dir)
        except all_errors:
            pass

    @staticmethod
    def _normalize_path(value: str) -> str:
        raw = (value or "").strip().replace("\\", "/")
        if not raw:
            return ""
        if raw == "/":
            return raw
        normalized = posixpath.normpath(raw)
        if raw.startswith("/") and not normalized.startswith("/"):
            normalized = "/" + normalized
        return normalized
