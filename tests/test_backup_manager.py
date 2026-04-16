"""Tests for windrose_deployer.core.backup_manager."""
import time
import pytest
from pathlib import Path

from windrose_deployer.core.backup_manager import (
    BackupManager,
    BackupRecord,
    DEFAULT_MAX_BACKUPS_PER_SOURCE,
)


class TestBackupManager:
    def test_backup_and_list(self, tmp_path):
        src_file = tmp_path / "original.txt"
        src_file.write_text("hello")
        backup_root = tmp_path / "backups"
        mgr = BackupManager(backup_root)

        record = mgr.backup_file(src_file, category="installs", description="test")
        assert record is not None
        assert Path(record.backup_path).is_file()
        assert len(mgr.list_backups()) == 1

    def test_restore(self, tmp_path):
        src_file = tmp_path / "original.txt"
        src_file.write_text("version1")
        backup_root = tmp_path / "backups"
        mgr = BackupManager(backup_root)

        record = mgr.backup_file(src_file, category="installs")
        src_file.write_text("version2")
        assert mgr.restore_backup(record)
        assert src_file.read_text() == "version1"

    def test_latest_backup(self, tmp_path):
        src_file = tmp_path / "data.json"
        src_file.write_text("v1")
        backup_root = tmp_path / "backups"
        mgr = BackupManager(backup_root)

        r1 = mgr.backup_file(src_file, category="server_config", description="first")
        time.sleep(0.05)
        src_file.write_text("v2")
        r2 = mgr.backup_file(src_file, category="server_config", description="second")

        latest = mgr.latest_backup(category="server_config")
        assert latest is not None
        assert latest.backup_id == r2.backup_id

    def test_latest_backup_empty(self, tmp_path):
        mgr = BackupManager(tmp_path / "backups")
        assert mgr.latest_backup() is None

    def test_backup_nonexistent_file(self, tmp_path):
        mgr = BackupManager(tmp_path / "backups")
        result = mgr.backup_file(tmp_path / "ghost.txt")
        assert result is None

    def test_category_filter(self, tmp_path):
        src = tmp_path / "f.txt"
        src.write_text("x")
        mgr = BackupManager(tmp_path / "backups")
        mgr.backup_file(src, category="installs")
        mgr.backup_file(src, category="server_config")
        mgr.backup_file(src, category="world_config")

        assert len(mgr.list_backups("installs")) == 1
        assert len(mgr.list_backups("server_config")) == 1
        assert len(mgr.list_backups("world_config")) == 1
        assert len(mgr.list_backups()) == 3

    def test_delete_backup_removes_record_and_file(self, tmp_path):
        src = tmp_path / "f.txt"
        src.write_text("x")
        mgr = BackupManager(tmp_path / "backups")
        record = mgr.backup_file(src, category="installs")

        assert record is not None
        assert Path(record.backup_path).exists()
        assert mgr.delete_backup(record)
        assert not Path(record.backup_path).exists()
        assert mgr.list_backups() == []

    def test_from_dict_resilient(self):
        record = BackupRecord.from_dict({"backup_id": "x", "timestamp": "t"})
        assert record.backup_id == "x"
        assert record.category == "installs"

    def test_auto_retention_keeps_last_10_per_source(self, tmp_path):
        src = tmp_path / "rotating.txt"
        backup_root = tmp_path / "backups"
        mgr = BackupManager(backup_root)

        for idx in range(DEFAULT_MAX_BACKUPS_PER_SOURCE + 2):
            src.write_text(f"v{idx}", encoding="utf-8")
            mgr.backup_file(src, category="installs")

        records = mgr.list_backups(source_path=src)
        assert len(records) == DEFAULT_MAX_BACKUPS_PER_SOURCE

        saved_versions = [Path(record.backup_path).read_text(encoding="utf-8") for record in records]
        assert saved_versions == [f"v{idx}" for idx in range(2, 12)]

    def test_manual_prune_retention_respects_source_profile_groups(self, tmp_path):
        mgr = BackupManager(tmp_path / "backups", max_backups_per_source=None)
        profile_a = "remote://profile-a/game/R5/ServerDescription.json"
        profile_b = "remote://profile-b/game/R5/ServerDescription.json"

        for idx in range(12):
            mgr.backup_bytes(
                source_path=profile_a,
                filename="ServerDescription.json",
                data=f"a{idx}".encode("utf-8"),
                category="remote_server_config",
            )
        for idx in range(3):
            mgr.backup_bytes(
                source_path=profile_b,
                filename="ServerDescription.json",
                data=f"b{idx}".encode("utf-8"),
                category="remote_server_config",
            )

        pruned = mgr.prune_retention(max_backups_per_source=10)

        assert pruned == 2
        assert len(mgr.list_backups(source_path=profile_a)) == 10
        assert len(mgr.list_backups(source_path=profile_b)) == 3
