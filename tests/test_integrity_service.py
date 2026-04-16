"""Tests for verify/repair recovery helpers."""
from pathlib import Path
import zipfile

from windrose_deployer.core.backup_manager import BackupManager
from windrose_deployer.core.deployment_planner import DeploymentPlan, PlannedFile
from windrose_deployer.core.installer import Installer
from windrose_deployer.core.integrity_service import IntegrityService
from windrose_deployer.models.app_paths import AppPaths
from windrose_deployer.models.mod_install import InstallTarget


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    archive_dir = tmp_path / "archives"
    client_root = tmp_path / "client"
    mod_dir = client_root / "R5" / "Content" / "Paks" / "~mods"
    archive_dir.mkdir(parents=True)
    mod_dir.mkdir(parents=True)
    return archive_dir, client_root, mod_dir


def test_verify_detects_modified_file(tmp_path: Path) -> None:
    archive_dir, client_root, mod_dir = _workspace(tmp_path)
    backup = BackupManager(tmp_path / "backups")
    installer = Installer(backup)

    archive = archive_dir / "verify.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("verify_mod.pak", "expected-data")

    plan = DeploymentPlan(
        mod_name="VerifyMod",
        archive_path=str(archive),
        target=InstallTarget.CLIENT,
        install_type="pak_only",
    )
    plan.files.append(PlannedFile(
        archive_entry_path="verify_mod.pak",
        dest_path=mod_dir / "verify_mod.pak",
        is_pak=True,
    ))

    mod, _ = installer.install(plan)
    (mod_dir / "verify_mod.pak").write_text("changed", encoding="utf-8")

    integrity = IntegrityService(AppPaths(client_root=client_root), backup)
    result = integrity.verify_mod(mod)

    assert not result.ok
    assert any(issue.reason == "modified" for issue in result.issues)


def test_repair_restores_expected_bytes(tmp_path: Path) -> None:
    archive_dir, client_root, mod_dir = _workspace(tmp_path)
    backup = BackupManager(tmp_path / "backups")
    installer = Installer(backup)

    archive = archive_dir / "repair.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("repair_mod.pak", "expected-data")

    plan = DeploymentPlan(
        mod_name="RepairMod",
        archive_path=str(archive),
        target=InstallTarget.CLIENT,
        install_type="pak_only",
    )
    plan.files.append(PlannedFile(
        archive_entry_path="repair_mod.pak",
        dest_path=mod_dir / "repair_mod.pak",
        is_pak=True,
    ))

    mod, _ = installer.install(plan)
    target_file = mod_dir / "repair_mod.pak"
    target_file.write_text("corrupted", encoding="utf-8")

    integrity = IntegrityService(AppPaths(client_root=client_root), backup)
    result = integrity.repair_mod(mod)

    assert result.failed == []
    assert str(target_file) in result.repaired
    assert target_file.read_text(encoding="utf-8") == "expected-data"
