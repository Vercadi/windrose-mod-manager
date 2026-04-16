from pathlib import Path

import pytest

from windrose_deployer.core.sftp_provider import SftpProvider


def test_resolve_private_key_path_accepts_existing_file(tmp_path: Path) -> None:
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("dummy", encoding="utf-8")

    resolved = SftpProvider._resolve_private_key_path(str(key_path))

    assert resolved == str(key_path)


def test_resolve_private_key_path_rejects_inline_key_contents() -> None:
    with pytest.raises(ValueError, match="file path"):
        SftpProvider._resolve_private_key_path("line1\nline2")


def test_resolve_private_key_path_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing_key"

    with pytest.raises(FileNotFoundError):
        SftpProvider._resolve_private_key_path(str(missing))
