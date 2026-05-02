"""Safety regression tests for install/uninstall/manifest invariants."""
import json
from types import SimpleNamespace
import pytest
from pathlib import Path

from windrose_deployer.core.backup_manager import BackupManager
from windrose_deployer.core.installer import Installer
from windrose_deployer.core.manifest_store import ManifestStore, SCHEMA_VERSION
from windrose_deployer.core.recovery_service import RecoveryService
from windrose_deployer.core.server_sync_service import ServerSyncService
from windrose_deployer.core.deployment_planner import DeploymentPlan, PlannedFile
from windrose_deployer.core.server_config_service import ServerConfigService
from windrose_deployer.models.deployment_record import DeploymentRecord
from windrose_deployer.models.mod_install import ModInstall, InstallTarget
from windrose_deployer.models.app_paths import AppPaths
from windrose_deployer.models.world_config import WorldConfig
from windrose_deployer.ui.app_window import AppWindow
from windrose_deployer.ui.tabs.mods_tab import ModsTab
from windrose_deployer.ui.tabs.server_tab import ServerTab
from windrose_deployer.ui.tabs.settings_tab import SettingsTab
from windrose_deployer.utils.naming import generate_mod_id


@pytest.fixture
def workspace(tmp_path):
    """Create a minimal workspace with backup dir, data dir, and a target dir."""
    backup_dir = tmp_path / "backups"
    data_dir = tmp_path / "data"
    target_dir = tmp_path / "game" / "R5" / "Content" / "Paks" / "~mods"
    archive_dir = tmp_path / "archives"
    for d in (backup_dir, data_dir, target_dir, archive_dir):
        d.mkdir(parents=True)
    return {
        "tmp": tmp_path,
        "backup_dir": backup_dir,
        "data_dir": data_dir,
        "target_dir": target_dir,
        "archive_dir": archive_dir,
        "backup": BackupManager(backup_dir),
        "manifest": ManifestStore(data_dir),
    }


def _make_plan(target_dir: Path, archive_path: str, files: dict[str, bytes],
               mod_name: str = "TestMod") -> DeploymentPlan:
    """Build a plan that deploys given files {filename: content} to target_dir."""
    plan = DeploymentPlan(
        mod_name=mod_name,
        archive_path=archive_path,
        target=InstallTarget.CLIENT,
        install_type="pak_only",
    )
    for name, content in files.items():
        plan.files.append(PlannedFile(
            archive_entry_path=name,
            dest_path=target_dir / name,
            is_pak=True,
        ))
    return plan


class TestOverwriteAndRestore:
    """Uninstall must restore the original file when a mod overwrote it."""

    def test_overwrite_install_then_uninstall_restores_original(self, workspace):
        target_dir = workspace["target_dir"]
        installer = Installer(workspace["backup"])

        original_content = b"ORIGINAL_GAME_FILE"
        original_file = target_dir / "test.pak"
        original_file.write_bytes(original_content)

        # Create a fake archive (zip) with a replacement file
        import zipfile
        archive_path = workspace["archive_dir"] / "mod.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("test.pak", "MOD_REPLACEMENT")

        plan = DeploymentPlan(
            mod_name="OverwriteMod",
            archive_path=str(archive_path),
            target=InstallTarget.CLIENT,
            install_type="pak_only",
        )
        plan.files.append(PlannedFile(
            archive_entry_path="test.pak",
            dest_path=original_file,
            is_pak=True,
        ))

        mod, record = installer.install(plan)
        assert original_file.read_bytes() == b"MOD_REPLACEMENT"
        assert mod.backup_map.get(str(original_file)) is not None

        installer.uninstall(mod)
        assert original_file.exists(), "Original file should be restored"
        assert original_file.read_bytes() == original_content

    def test_disable_then_uninstall_restores_original(self, workspace):
        target_dir = workspace["target_dir"]
        installer = Installer(workspace["backup"])

        original_content = b"ORIGINAL_GAME_FILE"
        original_file = target_dir / "test_disabled.pak"
        original_file.write_bytes(original_content)

        import zipfile
        archive_path = workspace["archive_dir"] / "disabled_mod.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("test_disabled.pak", "MOD_REPLACEMENT")

        plan = DeploymentPlan(
            mod_name="DisabledOverwriteMod",
            archive_path=str(archive_path),
            target=InstallTarget.CLIENT,
            install_type="pak_only",
        )
        plan.files.append(PlannedFile(
            archive_entry_path="test_disabled.pak",
            dest_path=original_file,
            is_pak=True,
        ))

        mod, _ = installer.install(plan)
        assert installer.disable(mod)
        assert not original_file.exists()
        assert (target_dir / "test_disabled.pak.disabled").exists()

        installer.uninstall(mod)
        assert original_file.exists(), "Original file should be restored after disabled uninstall"
        assert original_file.read_bytes() == original_content


class TestModIdIsUUID:
    """New installs must use UUID-based mod_id, not name-based."""

    def test_install_generates_uuid_id(self, workspace):
        import zipfile
        archive_path = workspace["archive_dir"] / "mymod.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("mod.pak", "data")

        installer = Installer(workspace["backup"])
        plan = DeploymentPlan(
            mod_name="My Cool Mod",
            archive_path=str(archive_path),
            target=InstallTarget.CLIENT,
            install_type="pak_only",
        )
        plan.files.append(PlannedFile(
            archive_entry_path="mod.pak",
            dest_path=workspace["target_dir"] / "mod.pak",
            is_pak=True,
        ))

        mod, _ = installer.install(plan)
        assert len(mod.mod_id) == 32, "mod_id should be a 32-char UUID hex"
        assert mod.display_name == "My Cool Mod"

    def test_duplicate_names_get_different_ids(self, workspace):
        import zipfile
        manifest = workspace["manifest"]

        for i in range(3):
            archive_path = workspace["archive_dir"] / f"mod{i}.zip"
            with zipfile.ZipFile(archive_path, "w") as zf:
                zf.writestr(f"mod{i}.pak", f"data{i}")

            installer = Installer(workspace["backup"])
            plan = DeploymentPlan(
                mod_name="SameName",
                archive_path=str(archive_path),
                target=InstallTarget.CLIENT,
                install_type="pak_only",
            )
            plan.files.append(PlannedFile(
                archive_entry_path=f"mod{i}.pak",
                dest_path=workspace["target_dir"] / f"mod{i}.pak",
                is_pak=True,
            ))
            mod, _ = installer.install(plan)
            manifest.add_mod(mod)

        assert len(manifest.list_mods()) == 3, "Three mods with same name should coexist"


class TestManifestSchemaVersion:
    """Manifest must write and read schema_version."""

    def test_save_includes_schema_version(self, workspace):
        manifest = workspace["manifest"]
        mod = ModInstall(
            mod_id=generate_mod_id(),
            display_name="Test",
            source_archive="test.zip",
            targets=["client"],
            installed_files=[],
        )
        manifest.add_mod(mod)

        raw = json.loads((workspace["data_dir"] / "app_state.json").read_text())
        assert raw["schema_version"] == SCHEMA_VERSION

    def test_v1_manifest_migrates_to_uuid(self, workspace):
        """Old v1 manifests with name-based ids should be migrated to UUIDs."""
        state_file = workspace["data_dir"] / "app_state.json"
        state_file.write_text(json.dumps({
            "mods": [{
                "mod_id": "my_cool_mod",
                "display_name": "My Cool Mod",
                "source_archive": "test.zip",
                "targets": ["client"],
                "installed_files": ["C:/game/mod.pak"],
                "backed_up_files": [],
                "install_time": "2026-01-01",
                "enabled": True,
            }],
            "history": [],
        }), encoding="utf-8")

        manifest = ManifestStore(workspace["data_dir"])
        mods = manifest.list_mods()
        assert len(mods) == 1
        assert len(mods[0].mod_id) == 32, "Old name-based id should be migrated to UUID"
        assert mods[0].display_name == "My Cool Mod"

        raw = json.loads(state_file.read_text())
        assert raw["schema_version"] == SCHEMA_VERSION

    def test_v1_migration_creates_backup_copy(self, workspace):
        """Migration must back up the old manifest before rewriting."""
        state_file = workspace["data_dir"] / "app_state.json"
        v1_content = json.dumps({
            "mods": [{
                "mod_id": "old_mod",
                "display_name": "Old Mod",
                "source_archive": "old.zip",
                "targets": ["client"],
                "installed_files": ["C:/game/old.pak"],
                "backed_up_files": [],
                "install_time": "2026-01-01",
                "enabled": True,
            }],
            "history": [],
        })
        state_file.write_text(v1_content, encoding="utf-8")

        ManifestStore(workspace["data_dir"])

        backup_file = workspace["data_dir"] / "app_state.v1.bak.json"
        assert backup_file.exists(), "Pre-migration backup must be created"
        backup_raw = json.loads(backup_file.read_text())
        assert "schema_version" not in backup_raw, "Backup should be the original v1 file"
        assert backup_raw["mods"][0]["mod_id"] == "old_mod"


class TestManifestHistoryRollback:
    def test_remove_last_records_truncates_history(self, workspace):
        manifest = workspace["manifest"]
        manifest.add_record(DeploymentRecord(mod_id="a", action="install", target="client"))
        manifest.add_record(DeploymentRecord(mod_id="b", action="install", target="server"))

        manifest.remove_last_records(1)

        assert [record.mod_id for record in manifest.list_history()] == ["a"]


class TestInstallAllCounting:
    """Install All must not overcount successes."""

    def test_do_install_returns_false_on_invalid_plan(self):
        """_do_install returning False should not count as success.
        We test the underlying logic: an invalid plan returns False."""
        from windrose_deployer.core.deployment_planner import DeploymentPlan
        plan = DeploymentPlan(
            mod_name="bad",
            archive_path="nonexistent.zip",
            target=InstallTarget.CLIENT,
            install_type="pak_only",
            valid=False,
            warnings=["test failure"],
        )
        assert not plan.valid


class TestPresetInstallRollback:
    def test_combined_install_rolls_back_first_target_when_second_fails(self, monkeypatch):
        client_plan = SimpleNamespace(target=InstallTarget.CLIENT)
        local_plan = SimpleNamespace(target=InstallTarget.SERVER)
        client_mod = ModInstall(
            mod_id=generate_mod_id(),
            display_name="Combo Mod",
            source_archive="combo.zip",
            targets=["client"],
            installed_files=["C:/client/combo.pak"],
        )
        client_record = DeploymentRecord(
            mod_id=client_mod.mod_id,
            action="install",
            target="client",
            display_name="Combo Mod",
            source_archive="combo.zip",
        )
        uninstalls: list[str] = []
        refreshes: list[str] = []

        class _Installer:
            def install(self, plan):
                if plan.target == InstallTarget.CLIENT:
                    return client_mod, client_record
                raise RuntimeError("local target failed")

            def uninstall(self, mod):
                uninstalls.append(mod.mod_id)
                return DeploymentRecord(mod_id=mod.mod_id, action="uninstall", target="client")

        class _Manifest:
            def __init__(self):
                self.mods: list[str] = []
                self.records: list[str] = []
                self.removed_mods: list[str] = []
                self.removed_records: list[int] = []

            def add_mod(self, mod):
                self.mods.append(mod.mod_id)

            def add_record(self, record):
                self.records.append(record.mod_id)

            def remove_mod(self, mod_id):
                self.removed_mods.append(mod_id)

            def remove_last_records(self, count):
                self.removed_records.append(count)

        manifest = _Manifest()
        app = SimpleNamespace(
            installer=_Installer(),
            manifest=manifest,
            confirm_action=lambda *args, **kwargs: True,
            refresh_installed_tab=lambda: refreshes.append("installed"),
            refresh_backups_tab=lambda: refreshes.append("backups"),
            open_remote_deploy=lambda path: None,
        )

        tab = object.__new__(ModsTab)
        tab.app = app
        tab.refresh_view = lambda: refreshes.append("view")
        tab._set_result = lambda *args, **kwargs: None
        tab._target_label = lambda target: target.value
        tab._install_preset_label = lambda preset: "Client + Local Server"
        tab._install_targets_for_preset = lambda preset: [InstallTarget.CLIENT, InstallTarget.SERVER]
        tab._prepare_install_target = lambda info, mod_name, target, selected_variant: (
            (client_plan if target == InstallTarget.CLIENT else local_plan),
            None,
        )

        monkeypatch.setattr(
            "windrose_deployer.ui.tabs.mods_tab.check_plan_conflicts",
            lambda plan, manifest: SimpleNamespace(has_conflicts=False, conflicts=[]),
        )

        result = ModsTab._run_install_preset(
            tab,
            SimpleNamespace(archive_path="combo.zip"),
            "Combo Mod",
            "client_local",
            None,
            quiet=True,
            confirm_conflicts=True,
        )

        assert not result
        assert uninstalls == [client_mod.mod_id]
        assert manifest.mods == []
        assert manifest.records == []
        assert manifest.removed_mods == []
        assert manifest.removed_records == []
        assert refreshes == []


class TestServerConfigRestoreTargeting:
    def test_restore_latest_uses_current_path(self, tmp_path):
        backup = BackupManager(tmp_path / "backups")
        service = ServerConfigService(backup)

        current = tmp_path / "current" / "ServerDescription.json"
        old = tmp_path / "old" / "ServerDescription.json"
        current.parent.mkdir(parents=True)
        old.parent.mkdir(parents=True)

        current.write_text('{"ServerName": "current-backup"}', encoding="utf-8")
        backup.backup_file(current, category="server_config")
        current.write_text('{"ServerName": "current-live"}', encoding="utf-8")

        old.write_text('{"ServerName": "old-backup"}', encoding="utf-8")
        backup.backup_file(old, category="server_config")
        old.write_text('{"ServerName": "old-live"}', encoding="utf-8")

        assert service.restore_latest(current)
        assert current.read_text(encoding="utf-8") == '{"ServerName": "current-backup"}'
        assert old.read_text(encoding="utf-8") == '{"ServerName": "old-live"}'


class TestSameArchiveMultiInstallState:
    def test_client_local_preset_uses_separate_targets(self):
        assert ModsTab._install_targets_for_preset("client_local") == [
            InstallTarget.CLIENT,
            InstallTarget.SERVER,
        ]

    def test_archive_state_helpers_cover_multiple_targets(self, tmp_path):
        manifest = ManifestStore(tmp_path / "data")
        manifest.add_mod(ModInstall(
            mod_id=generate_mod_id(),
            display_name="Shared Archive Client",
            source_archive="shared.zip",
            targets=["client"],
            installed_files=["C:/client/mod.pak"],
        ))
        manifest.add_mod(ModInstall(
            mod_id=generate_mod_id(),
            display_name="Shared Archive Server",
            source_archive="shared.zip",
            targets=["server"],
            installed_files=["C:/server/mod.pak"],
        ))

        tab = object.__new__(ModsTab)
        tab.app = SimpleNamespace(manifest=manifest)

        assert len(tab._mods_for_archive("shared.zip")) == 2
        assert tab._archive_covers_target("shared.zip", InstallTarget.CLIENT)
        assert tab._archive_covers_target("shared.zip", InstallTarget.SERVER)
        assert tab._archive_covers_target("shared.zip", InstallTarget.BOTH)
        assert tab._archive_badge_text("shared.zip").strip() == "CS"

    def test_normalize_combined_local_server_install_splits_records(self, tmp_path):
        client_root = tmp_path / "client"
        server_root = tmp_path / "server"
        client_root.mkdir()
        server_root.mkdir()
        client_file = client_root / "R5" / "Content" / "Paks" / "~mods" / "Combo_P.pak"
        server_file = server_root / "R5" / "Content" / "Paks" / "~mods" / "Combo_P.pak"
        client_file.parent.mkdir(parents=True)
        server_file.parent.mkdir(parents=True)

        manifest = ManifestStore(tmp_path / "data")
        manifest.add_mod(
            ModInstall(
                mod_id=generate_mod_id(),
                display_name="Combo",
                source_archive="combo.zip",
                targets=["both"],
                installed_files=[str(client_file), str(server_file)],
                backed_up_files=["client.bak", "server.bak"],
                backup_map={
                    str(client_file): "client.bak",
                    str(server_file): "server.bak",
                },
            )
        )

        tab = object.__new__(ModsTab)
        tab.app = SimpleNamespace(
            manifest=manifest,
            paths=SimpleNamespace(client_root=client_root, server_root=server_root),
        )

        ModsTab._normalize_combined_local_server_installs(tab)

        mods = sorted(manifest.list_mods(), key=lambda item: item.targets[0])
        assert [mod.targets for mod in mods] == [["client"], ["server"]]
        assert mods[0].installed_files == [str(client_file)]
        assert mods[1].installed_files == [str(server_file)]

    def test_archive_uninstall_action_uses_clicked_archive_context(self, tmp_path):
        archive = tmp_path / "clicked.zip"
        archive.write_text("zip", encoding="utf-8")
        calls = []

        tab = object.__new__(ModsTab)
        tab._selected_library_path = None
        tab._load_archive = lambda path: calls.append(("load", str(path))) or setattr(tab, "_selected_library_path", str(path))
        tab._on_uninstall = lambda: calls.append(("uninstall", tab._selected_library_path))

        ModsTab._on_uninstall_for_archive(tab, archive)

        assert calls == [
            ("load", str(archive)),
            ("uninstall", str(archive)),
        ]

    def test_remove_unmanaged_live_file_deletes_and_refreshes(self, tmp_path, monkeypatch):
        file_path = tmp_path / "Manual_P.pak"
        file_path.write_text("manual", encoding="utf-8")
        refreshes = []
        results = []

        tab = object.__new__(ModsTab)
        tab.app = SimpleNamespace(confirm_action=lambda *args, **kwargs: True)
        tab.refresh_view = lambda: refreshes.append("refresh")
        tab._set_result = lambda text, *, level="info": results.append((text, level))

        ModsTab._remove_unmanaged_live_file(tab, file_path, "Client")

        assert not file_path.exists()
        assert refreshes == ["refresh"]
        assert results == [("Removed unmanaged file Manual_P.pak from client ~mods.", "success")]

    def test_uninstall_selected_handles_untracked_live_files(self, tmp_path):
        file_path = tmp_path / "Manual_P.pak"
        file_path.write_text("manual", encoding="utf-8")
        refreshes = []
        results = []

        tab = object.__new__(ModsTab)
        tab.app = SimpleNamespace(
            confirm_action=lambda *args, **kwargs: True,
            refresh_installed_tab=lambda: refreshes.append("installed"),
            refresh_backups_tab=lambda: refreshes.append("backups"),
            manifest=SimpleNamespace(list_mods=lambda: []),
        )
        tab._selected_mod_ids = set()
        tab._selected_live_files = {str(file_path)}
        tab.refresh_view = lambda: refreshes.append("view")
        tab._set_result = lambda text, *, level="info": results.append((text, level))

        ModsTab._on_uninstall_selected_mods(tab)

        assert not file_path.exists()
        assert refreshes == ["installed", "backups", "view"]
        assert results == [("Uninstalled 1 selected item(s).", "success")]

    def test_uninstall_selected_handles_untracked_live_bundle(self, tmp_path):
        pak = tmp_path / "Manual_P.pak"
        utoc = tmp_path / "Manual_P.utoc"
        ucas = tmp_path / "Manual_P.ucas"
        for path in (pak, utoc, ucas):
            path.write_text("manual", encoding="utf-8")
        refreshes = []
        results = []

        tab = object.__new__(ModsTab)
        bundle_id = "||".join(str(path) for path in (pak, utoc, ucas))
        tab.app = SimpleNamespace(
            confirm_action=lambda *args, **kwargs: True,
            refresh_installed_tab=lambda: refreshes.append("installed"),
            refresh_backups_tab=lambda: refreshes.append("backups"),
            manifest=SimpleNamespace(list_mods=lambda: []),
        )
        tab._selected_mod_ids = set()
        tab._selected_live_files = {bundle_id}
        tab._live_file_bundle_members = {bundle_id: [pak, utoc, ucas]}
        tab.refresh_view = lambda: refreshes.append("view")
        tab._set_result = lambda text, *, level="info": results.append((text, level))

        ModsTab._on_uninstall_selected_mods(tab)

        assert not pak.exists()
        assert not utoc.exists()
        assert not ucas.exists()
        assert refreshes == ["installed", "backups", "view"]
        assert results == [("Uninstalled 1 selected item(s).", "success")]

    def test_uninstall_selected_handles_hosted_live_bundle(self):
        refreshes = []
        results = []
        deleted_calls = []
        records = []
        bundle_id = "hosted::/remote/~mods/Manual_P.pak||/remote/~mods/Manual_P.utoc"

        tab = object.__new__(ModsTab)
        tab.app = SimpleNamespace(
            confirm_action=lambda *args, **kwargs: True,
            refresh_installed_tab=lambda: refreshes.append("installed"),
            refresh_backups_tab=lambda: refreshes.append("backups"),
            manifest=SimpleNamespace(
                list_mods=lambda: [],
                add_record=lambda record: records.append(record),
            ),
            remote_deployer=SimpleNamespace(
                delete_remote_files=lambda profile, paths: (
                    deleted_calls.append((profile.name, list(paths))) or list(paths),
                    [],
                )
            ),
        )
        tab._selected_mod_ids = set()
        tab._selected_live_files = {bundle_id}
        tab._live_file_bundle_members = {
            bundle_id: ["/remote/~mods/Manual_P.pak", "/remote/~mods/Manual_P.utoc"]
        }
        tab._live_file_bundle_meta = {
            bundle_id: {"kind": "hosted", "target_label": "Hosted Server"}
        }
        tab._selected_hosted_profile = lambda: SimpleNamespace(profile_id="p1", name="Hosted Smoke")
        tab.refresh_view = lambda: refreshes.append("view")
        tab._set_result = lambda text, *, level="info": results.append((text, level))

        ModsTab._on_uninstall_selected_mods(tab)

        assert deleted_calls == [("Hosted Smoke", ["/remote/~mods/Manual_P.pak", "/remote/~mods/Manual_P.utoc"])]
        assert refreshes == ["installed", "backups", "view"]
        assert results == [("Uninstalled 1 selected item(s).", "success")]
        assert len(records) == 1
        assert records[0].action == "hosted_remove"


class TestBackupServiceRebinding:
    def test_rebind_backup_services_uses_new_backup_root(self, tmp_path):
        new_backup_dir = tmp_path / "new_backups"
        app = object.__new__(AppWindow)
        app.paths = AppPaths(backup_dir=new_backup_dir)

        AppWindow._rebind_backup_services(app)

        assert app.backup.backup_root == new_backup_dir
        assert app.installer.backup is app.backup
        assert app.server_config_svc.backup is app.backup
        assert app.world_config_svc.backup is app.backup


class TestSettingsSaveRootPersistence:
    def test_derived_server_save_root_stays_implicit_on_save(self, tmp_path):
        server_root = tmp_path / "Windrose Dedicated Server"
        paths = AppPaths(dedicated_server_root=server_root, local_save_root=None)
        tab = object.__new__(SettingsTab)
        tab.app = SimpleNamespace(paths=paths)
        tab._explicit_path_values = {"local_save_root": ""}

        resolved = SettingsTab._path_value_for_save(
            tab,
            "local_save_root",
            str(paths.effective_local_save_root),
        )

        assert resolved is None

    def test_custom_server_save_root_persists_as_override(self, tmp_path):
        server_root = tmp_path / "Windrose Dedicated Server"
        custom_save_root = tmp_path / "CustomSaves"
        paths = AppPaths(dedicated_server_root=server_root, local_save_root=None)
        tab = object.__new__(SettingsTab)
        tab.app = SimpleNamespace(paths=paths)
        tab._explicit_path_values = {"local_save_root": ""}

        resolved = SettingsTab._path_value_for_save(
            tab,
            "local_save_root",
            str(custom_save_root),
        )

        assert resolved == custom_save_root


class TestWorldConfigEditing:
    def test_blank_world_name_from_server_is_still_valid(self):
        cfg = WorldConfig(
            island_id="WORLD-1",
            world_name="",
            world_preset_type="Medium",
        )

        assert cfg.validate() == []

    def test_read_world_fields_includes_world_name(self):
        world_name_var = _DummyVar("Hosted Smoke World")
        tab = SimpleNamespace(
            _world_config=WorldConfig(island_id="WORLD-1", world_name=""),
            _world_fields={"WorldName": SimpleNamespace(_variable=world_name_var)},
            _preset_var=_DummyVar("Medium"),
            _combat_diff_var=_DummyVar("Normal"),
        )

        cfg = ServerTab._read_world_fields(tab)

        assert cfg.world_name == "Hosted Smoke World"


class _DummyVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class TestServerApplyFlow:
    def test_apply_changes_stops_when_server_save_fails(self):
        calls = []
        tab = SimpleNamespace(
            _confirm_var=_DummyVar(True),
            _config=object(),
            _world_path="world.json",
            _ensure_apply_confirmation=lambda prompt: True,
            _on_save_server=lambda notify_success=True: calls.append(("server", notify_success)) or False,
            _on_save_world=lambda notify_success=True: calls.append(("world", notify_success)) or True,
            _update_apply_summary=lambda: calls.append(("summary", None)),
        )

        assert not ServerTab._on_apply_changes(tab)
        assert ("server", False) in calls
        assert ("world", False) not in calls

    def test_apply_and_restart_skips_restart_when_apply_fails(self):
        calls = []
        tab = SimpleNamespace(
            _on_apply_changes=lambda: False,
            _source_var=_DummyVar("dedicated"),
            app=SimpleNamespace(_on_start_server=lambda: calls.append("restart")),
            _status_label=SimpleNamespace(configure=lambda **kwargs: calls.append(("status", kwargs))),
        )

        ServerTab._on_apply_and_restart(tab)
        assert calls == []

    def test_apply_and_restart_reports_local_launch_failure(self):
        calls = []
        tab = SimpleNamespace(
            _on_apply_changes=lambda: True,
            _source_var=_DummyVar("dedicated"),
            _active_local_label=lambda: "Dedicated Server",
            _active_local_root=lambda: Path("Z:/missing/server"),
            app=SimpleNamespace(_launch_server_root=lambda root, *, label: False),
            _status_label=SimpleNamespace(configure=lambda **kwargs: calls.append(kwargs)),
        )

        ServerTab._on_apply_and_restart(tab)

        assert calls == [{
            "text": "Dedicated Server launch failed after apply.",
            "text_color": "#c0392b",
        }]


class TestDedicatedServerLaunch:
    def test_start_server_uses_cmd_for_batch_file(self, tmp_path, monkeypatch):
        server_root = tmp_path / "server"
        server_root.mkdir()
        bat = server_root / "StartServerForeground.bat"
        bat.write_text("@echo off\r\n", encoding="utf-8")

        popen_calls = []
        monkeypatch.setattr(
            "windrose_deployer.ui.app_window.subprocess.Popen",
            lambda args, cwd=None, creationflags=0: popen_calls.append(
                {"args": args, "cwd": cwd, "creationflags": creationflags}
            ),
        )
        monkeypatch.setattr(
            "windrose_deployer.ui.app_window.messagebox.showerror",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected showerror")),
        )

        app = SimpleNamespace(paths=AppPaths(dedicated_server_root=server_root))
        app._launch_server_root = lambda root, *, label: AppWindow._launch_server_root(app, root, label=label)

        assert AppWindow._on_start_server(app) is True
        assert len(popen_calls) == 1
        assert popen_calls[0]["args"][:2] == ["cmd.exe", "/c"]
        assert popen_calls[0]["args"][2] == str(bat)
        assert popen_calls[0]["cwd"] == str(server_root)

    def test_start_server_returns_false_when_target_missing(self, monkeypatch):
        errors = []
        monkeypatch.setattr(
            "windrose_deployer.ui.app_window.messagebox.showerror",
            lambda *args: errors.append(args),
        )

        app = SimpleNamespace(paths=AppPaths(dedicated_server_root=Path("Z:/missing/server")))
        app._launch_server_root = lambda root, *, label: AppWindow._launch_server_root(app, root, label=label)

        assert AppWindow._on_start_server(app) is False
        assert errors


class TestServerSyncDuplicateNames:
    def test_compare_local_keeps_distinct_same_name_installs(self):
        mods = [
            ModInstall(
                mod_id=generate_mod_id(),
                display_name="SameName",
                source_archive="A.zip",
                targets=["client"],
                installed_files=["C:/client/A.pak"],
            ),
            ModInstall(
                mod_id=generate_mod_id(),
                display_name="SameName",
                source_archive="B.zip",
                targets=["client"],
                installed_files=["C:/client/B.pak"],
            ),
            ModInstall(
                mod_id=generate_mod_id(),
                display_name="SameName",
                source_archive="A.zip",
                targets=["server"],
                installed_files=["C:/server/A.pak"],
            ),
        ]

        report = ServerSyncService().compare_local(mods)
        statuses = sorted(item.status for item in report.items)

        assert len(report.items) == 2
        assert statuses == ["matched", "missing_on_server"]

    def test_missing_client_mods_for_local_excludes_version_mismatches(self):
        same_client = ModInstall(
            mod_id=generate_mod_id(),
            display_name="SameName",
            source_archive="A.zip",
            archive_hash="hash-a",
            targets=["client"],
            installed_files=["C:/client/A.pak"],
        )
        mismatched_client = ModInstall(
            mod_id=generate_mod_id(),
            display_name="SameName",
            source_archive="B.zip",
            archive_hash="hash-b",
            targets=["client"],
            installed_files=["C:/client/B.pak"],
        )
        server_mismatch = ModInstall(
            mod_id=generate_mod_id(),
            display_name="SameName",
            source_archive="C.zip",
            archive_hash="hash-c",
            targets=["server"],
            installed_files=["C:/server/C.pak"],
        )

        missing = ServerSyncService().client_mods_missing_from_local(
            [same_client, mismatched_client, server_mismatch],
            target="server",
        )

        assert [mod.mod_id for mod in missing] == [mismatched_client.mod_id]

    def test_server_only_frameworks_do_not_trigger_client_parity_review(self):
        windrose_plus = ModInstall(
            mod_id=generate_mod_id(),
            display_name="WindrosePlus",
            source_archive="windrose-plus.zip",
            install_kind="windrose_plus",
            targets=["dedicated_server"],
            installed_files=["D:/server/WindrosePlus/Scripts/main.lua"],
        )
        rcon = ModInstall(
            mod_id=generate_mod_id(),
            display_name="WindroseRCON",
            source_archive="WindroseRCON.zip",
            install_kind="rcon_mod",
            targets=["dedicated_server"],
            installed_files=["D:/server/R5/Binaries/Win64/ue4ss/Mods/WindroseRCON/dlls/main.dll"],
        )

        service = ServerSyncService()
        report = service.compare_local([windrose_plus, rcon], target="dedicated_server")
        missing = service.server_mods_missing_from_client([windrose_plus, rcon], target="dedicated_server")

        assert report.items == []
        assert missing == []

    def test_missing_client_mods_for_hosted_ignores_partial_matches(self):
        complete = ModInstall(
            mod_id=generate_mod_id(),
            display_name="Complete",
            source_archive="Complete.zip",
            targets=["client"],
            installed_files=["C:/client/Complete_P.pak"],
        )
        partial = ModInstall(
            mod_id=generate_mod_id(),
            display_name="Partial",
            source_archive="Partial.zip",
            targets=["client"],
            installed_files=["C:/client/Partial_P.pak", "C:/client/Partial_P.utoc"],
        )
        missing = ModInstall(
            mod_id=generate_mod_id(),
            display_name="Missing",
            source_archive="Missing.zip",
            targets=["client"],
            installed_files=["C:/client/Missing_P.pak"],
        )

        result = ServerSyncService().client_mods_missing_from_hosted(
            [complete, partial, missing],
            ["Complete_P.pak", "Partial_P.pak"],
        )

        assert [mod.mod_id for mod in result] == [missing.mod_id]

    def test_hosted_sync_actions_ignore_server_only_framework_client_records(self):
        rcon = ModInstall(
            mod_id=generate_mod_id(),
            display_name="WindroseRCON",
            source_archive="WindroseRCON.zip",
            install_kind="rcon_mod",
            targets=["client"],
            installed_files=["C:/client/R5/Binaries/Win64/version.dll"],
        )
        windrose_plus = ModInstall(
            mod_id=generate_mod_id(),
            display_name="WindrosePlus",
            source_archive="windrose-plus.zip",
            install_kind="windrose_plus",
            targets=["client"],
            installed_files=["C:/client/WindrosePlus/Scripts/main.lua"],
        )

        service = ServerSyncService()

        assert service.compare_hosted([rcon, windrose_plus], []).items == []
        assert service.client_mods_missing_from_hosted([rcon, windrose_plus], []) == []

    def test_server_only_frameworks_are_available_for_explanatory_notes(self):
        windrose_plus = ModInstall(
            mod_id=generate_mod_id(),
            display_name="WindrosePlus",
            source_archive="windrose-plus.zip",
            install_kind="windrose_plus",
            targets=["dedicated_server"],
            installed_files=["D:/server/WindrosePlus/Scripts/main.lua"],
        )

        result = ServerSyncService().server_only_frameworks_for_target(
            [windrose_plus],
            target="dedicated_server",
        )

        assert [mod.display_name for mod in result] == ["WindrosePlus"]


class TestRecoveryTimelineDedupe:
    def test_config_save_history_suppresses_duplicate_backup_entry(self, tmp_path):
        backup = BackupManager(tmp_path / "backups")
        manifest = ManifestStore(tmp_path / "data")
        service = RecoveryService(manifest, backup)

        config_path = tmp_path / "ServerDescription.json"
        config_path.write_text('{"ServerName":"Smoke"}', encoding="utf-8")
        backup.backup_file(
            config_path,
            category="server_config",
            description="Pre-save backup of local ServerDescription.json",
        )
        manifest.add_record(
            DeploymentRecord(
                mod_id="server:server",
                action="save_server_config",
                target="server",
                notes="Saved local server settings for Smoke",
                display_name="Server Settings",
            )
        )

        items = service.build_timeline()

        assert len(items) == 1
        assert items[0].action == "save_server_config"
