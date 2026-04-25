from windrose_deployer.core.backup_manager import BackupManager
from windrose_deployer.core.framework_config_service import FrameworkConfigService


def test_framework_config_service_saves_known_config_with_backup(tmp_path):
    backup = BackupManager(tmp_path / "backups", max_backups_per_source=None)
    service = FrameworkConfigService(backup)
    root = tmp_path / "Windrose"
    config_path = root / "R5" / "Binaries" / "Win64" / "ue4ss" / "UE4SS-settings.ini"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("old=true\n", encoding="utf-8")

    saved = service.save_config(root, "ue4ss_settings", "new=true\n")

    assert saved == config_path
    assert config_path.read_text(encoding="utf-8") == "new=true\n"
    backups = backup.list_backups(category="framework_config", source_path=config_path)
    assert len(backups) == 1


def test_windrose_plus_paths_use_expected_files(tmp_path):
    service = FrameworkConfigService(BackupManager(tmp_path / "backups", max_backups_per_source=None))
    paths = service.windrose_plus_paths(tmp_path / "Server")

    assert paths is not None
    assert paths.install_script.name == "install.ps1"
    assert paths.build_script.as_posix().endswith("windrose_plus/tools/WindrosePlus-BuildPak.ps1")
    assert paths.launch_wrapper.name == "StartWindrosePlusServer.bat"
    assert paths.generated_multipliers_pak.name == "WindrosePlus_Multipliers_P.pak"


def test_windrose_plus_json_is_pretty_formatted_on_read_and_save(tmp_path):
    backup = BackupManager(tmp_path / "backups", max_backups_per_source=None)
    service = FrameworkConfigService(backup)
    root = tmp_path / "Server"
    config_path = root / "windrose_plus.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"multipliers":{"stack_size":2},"server":{"http_port":8780}}', encoding="utf-8")

    path, text = service.read_config(root, "windrose_plus_json")
    saved = service.save_config(root, "windrose_plus_json", text)

    assert path == config_path
    assert saved == config_path
    assert '"multipliers": {' in config_path.read_text(encoding="utf-8")
    assert '\n  "server": {' in config_path.read_text(encoding="utf-8")
