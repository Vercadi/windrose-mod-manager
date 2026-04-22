import posixpath

from windrose_deployer.core import ftp_provider
from windrose_deployer.models.remote_profile import RemoteProfile


class FakeFTP:
    def __init__(self):
        self.encoding = "utf-8"
        self.cwd_path = "/"
        self.files = {
            "/mods/existing.pak": b"pak-data",
        }
        self.directories = {"/", "/mods"}
        self.connected = None
        self.logged_in = None
        self.supports_mlsd = True
        self.supports_size = True

    def connect(self, host, port, timeout=10):
        self.connected = (host, port, timeout)

    def login(self, username, password):
        self.logged_in = (username, password)

    def quit(self):
        return None

    def close(self):
        return None

    def pwd(self):
        return self.cwd_path

    def cwd(self, path):
        normalized = self._normalize(path)
        if normalized not in self.directories:
            raise ftp_provider.error_perm("550 missing directory")
        self.cwd_path = normalized

    def size(self, path):
        if not self.supports_size:
            raise ftp_provider.error_perm("500 SIZE unsupported")
        normalized = self._normalize(path)
        if normalized not in self.files:
            raise ftp_provider.error_perm("550 missing file")
        return len(self.files[normalized])

    def mlsd(self, remote_dir):
        if not self.supports_mlsd:
            raise ftp_provider.error_perm("500 MLSD unsupported")
        normalized = self._normalize(remote_dir)
        seen = {}
        prefix = normalized.rstrip("/") + "/"
        for path in sorted(self.files):
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix):]
            child = remainder.split("/", 1)[0]
            seen[child] = "dir" if "/" in remainder else "file"
        for path in sorted(self.directories):
            if path == normalized or not path.startswith(prefix):
                continue
            remainder = path[len(prefix):]
            child = remainder.split("/", 1)[0]
            seen[child] = "dir"
        return [(name, {"type": kind}) for name, kind in seen.items()]

    def nlst(self, remote_dir):
        normalized = self._normalize(remote_dir)
        prefix = normalized.rstrip("/") + "/"
        entries = set()
        for path in self.files:
            if path.startswith(prefix):
                entries.add(prefix + path[len(prefix):].split("/", 1)[0])
        for path in self.directories:
            if path != normalized and path.startswith(prefix):
                entries.add(prefix + path[len(prefix):].split("/", 1)[0])
        return sorted(entries)

    def mkd(self, path):
        self.directories.add(self._normalize(path))

    def storbinary(self, command, handle):
        remote_path = command.split(" ", 1)[1]
        normalized = self._normalize(remote_path)
        self.directories.add(posixpath.dirname(normalized) or "/")
        self.files[normalized] = handle.read()

    def delete(self, remote_path):
        self.files.pop(self._normalize(remote_path), None)

    def retrbinary(self, command, callback):
        remote_path = command.split(" ", 1)[1]
        callback(self.files[self._normalize(remote_path)])

    @staticmethod
    def _normalize(path):
        raw = (path or "").replace("\\", "/")
        if not raw:
            return "/"
        normalized = posixpath.normpath(raw)
        if raw.startswith("/") and not normalized.startswith("/"):
            normalized = "/" + normalized
        return normalized


def _make_profile(protocol="ftp"):
    profile = RemoteProfile.new("Hosted FTP")
    profile.protocol = protocol
    profile.host = "example.com"
    profile.port = 21
    profile.username = "user"
    profile.password = "secret"
    return profile


def test_ftp_provider_supports_connect_list_upload_read_and_delete(monkeypatch):
    fake = FakeFTP()
    monkeypatch.setattr(ftp_provider, "FTP", lambda: fake)

    provider = ftp_provider.FtpProvider(_make_profile())

    entries = provider.list_entries("/mods")
    assert [entry.name for entry in entries] == ["existing.pak"]
    assert provider.path_exists("/mods")
    assert provider.path_exists("/mods/existing.pak")

    provider.upload_bytes(b"new-data", "/mods/nested/new_mod.pak")
    assert provider.read_bytes("/mods/nested/new_mod.pak") == b"new-data"
    provider.delete_file("/mods/nested/new_mod.pak")
    assert not provider.path_exists("/mods/nested/new_mod.pak")


def test_ftp_provider_falls_back_when_mlsd_is_unavailable(monkeypatch):
    fake = FakeFTP()
    fake.supports_mlsd = False
    fake.directories.add("/mods/folder")
    fake.files["/mods/folder/child.txt"] = b"child"
    monkeypatch.setattr(ftp_provider, "FTP", lambda: fake)

    provider = ftp_provider.FtpProvider(_make_profile())

    entries = provider.list_entries("/mods")

    assert {entry.name for entry in entries} == {"existing.pak", "folder"}
    assert any(entry.is_dir for entry in entries if entry.name == "folder")


def test_ftp_provider_path_exists_falls_back_to_parent_listing_when_size_unavailable(monkeypatch):
    fake = FakeFTP()
    fake.supports_size = False
    fake.files["/R5/ServerDescription.json"] = b"{}"
    fake.directories.add("/R5")
    monkeypatch.setattr(ftp_provider, "FTP", lambda: fake)

    provider = ftp_provider.FtpProvider(_make_profile())

    assert provider.path_exists("/R5/ServerDescription.json")
    assert provider.path_exists("R5/ServerDescription.json")
    assert not provider.path_exists("/R5/Missing.json")
