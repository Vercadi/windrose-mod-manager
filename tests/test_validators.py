"""Tests for windrose_deployer.core.validators."""
import tempfile
from pathlib import Path

from windrose_deployer.core.validators import (
    validate_client_root,
    validate_server_root,
    validate_local_config,
    validate_pak_target,
)


class TestValidateClientRoot:
    def test_missing_dir(self, tmp_path):
        ok, msg = validate_client_root(tmp_path / "nope")
        assert not ok

    def test_missing_exe(self, tmp_path):
        (tmp_path / "R5").mkdir()
        ok, msg = validate_client_root(tmp_path)
        assert not ok
        assert "Windrose.exe" in msg

    def test_missing_r5(self, tmp_path):
        (tmp_path / "Windrose.exe").touch()
        ok, msg = validate_client_root(tmp_path)
        assert not ok
        assert "R5" in msg

    def test_valid(self, tmp_path):
        (tmp_path / "Windrose.exe").touch()
        (tmp_path / "R5").mkdir()
        ok, msg = validate_client_root(tmp_path)
        assert ok


class TestValidateServerRoot:
    def test_valid(self, tmp_path):
        (tmp_path / "WindroseServer.exe").touch()
        (tmp_path / "R5").mkdir()
        ok, msg = validate_server_root(tmp_path)
        assert ok

    def test_missing_exe(self, tmp_path):
        ok, msg = validate_server_root(tmp_path)
        assert not ok

    def test_missing_r5(self, tmp_path):
        (tmp_path / "WindroseServer.exe").touch()
        ok, msg = validate_server_root(tmp_path)
        assert not ok
        assert "R5" in msg


class TestValidateLocalConfig:
    def test_valid_engine_ini(self, tmp_path):
        (tmp_path / "Engine.ini").touch()
        ok, msg = validate_local_config(tmp_path)
        assert ok

    def test_valid_game_settings(self, tmp_path):
        (tmp_path / "GameUserSettings.ini").touch()
        ok, msg = validate_local_config(tmp_path)
        assert ok

    def test_empty_dir(self, tmp_path):
        ok, msg = validate_local_config(tmp_path)
        assert not ok


class TestValidatePakTarget:
    def test_existing_dir(self, tmp_path):
        ok, msg = validate_pak_target(tmp_path)
        assert ok

    def test_mods_subdir_creatable(self, tmp_path):
        ok, msg = validate_pak_target(tmp_path / "~mods")
        assert ok

    def test_deeply_missing(self, tmp_path):
        ok, msg = validate_pak_target(tmp_path / "a" / "b" / "~mods")
        assert not ok
