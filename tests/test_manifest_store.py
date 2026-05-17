"""Tests for windrose_deployer.core.manifest_store."""
import json
import pytest
from pathlib import Path

from windrose_deployer.core.manifest_store import ManifestStore
from windrose_deployer.models.deployment_record import DeploymentRecord
from windrose_deployer.models.metadata import ModMetadata
from windrose_deployer.models.mod_install import ModInstall


def _make_mod(mod_id: str = "test_mod", files: list[str] | None = None) -> ModInstall:
    return ModInstall(
        mod_id=mod_id,
        display_name=mod_id.replace("_", " ").title(),
        source_archive="test.zip",
        archive_hash="abc123",
        install_type="pak_only",
        layout_kind="standard_pak_archive",
        target_root_hint="paks",
        selected_variant=None,
        selected_entries=["test.pak"],
        installed_archive_entries=["test.pak"],
        layout_warnings=["Support/metadata files were skipped during deployment planning."],
        targets=["client"],
        installed_files=files or ["C:/mods/test.pak"],
        backed_up_files=[],
        component_map={"test.pak": files or ["C:/mods/test.pak"]},
        metadata=ModMetadata(version_tag="1.0.0", nexus_mod_id="29"),
        enabled=True,
    )


class TestManifestStore:
    def test_add_and_get(self, tmp_path):
        store = ManifestStore(tmp_path)
        mod = _make_mod()
        store.add_mod(mod)
        assert store.get_mod("test_mod") is not None
        assert store.get_mod("nonexistent") is None

    def test_persistence(self, tmp_path):
        store = ManifestStore(tmp_path)
        store.add_mod(_make_mod())

        store2 = ManifestStore(tmp_path)
        assert store2.get_mod("test_mod") is not None
        assert store2.get_mod("test_mod").display_name == "Test Mod"

    def test_remove(self, tmp_path):
        store = ManifestStore(tmp_path)
        store.add_mod(_make_mod())
        removed = store.remove_mod("test_mod")
        assert removed is not None
        assert store.get_mod("test_mod") is None

    def test_update(self, tmp_path):
        store = ManifestStore(tmp_path)
        mod = _make_mod()
        store.add_mod(mod)
        mod.enabled = False
        store.update_mod(mod)

        store2 = ManifestStore(tmp_path)
        assert store2.get_mod("test_mod").enabled is False

    def test_files_map_excludes_disabled(self, tmp_path):
        store = ManifestStore(tmp_path)
        mod = _make_mod(files=["C:/game/mods/a.pak"])
        mod.enabled = False
        store.add_mod(mod)
        assert store.get_files_map() == {}

    def test_files_map_includes_enabled(self, tmp_path):
        store = ManifestStore(tmp_path)
        store.add_mod(_make_mod(files=["C:/game/mods/a.pak"]))
        fmap = store.get_files_map()
        assert "C:/game/mods/a.pak" in fmap

    def test_corrupt_json_recovery(self, tmp_path):
        state_file = tmp_path / "app_state.json"
        state_file.write_text("{invalid json", encoding="utf-8")
        store = ManifestStore(tmp_path)
        assert store.list_mods() == []

    def test_corrupt_entry_skipped(self, tmp_path):
        state_file = tmp_path / "app_state.json"
        state_file.write_text(json.dumps({
            "mods": [
                {"bad_key": "no_mod_id"},
                _make_mod().to_dict(),
            ],
            "history": [],
        }), encoding="utf-8")
        store = ManifestStore(tmp_path)
        assert len(store.list_mods()) == 1

    def test_metadata_and_component_map_round_trip(self, tmp_path):
        store = ManifestStore(tmp_path)
        mod = _make_mod()
        store.add_mod(mod)

        loaded = ManifestStore(tmp_path).get_mod("test_mod")
        assert loaded is not None
        assert loaded.metadata.version_tag == "1.0.0"
        assert loaded.metadata.nexus_mod_id == "29"
        assert loaded.component_map == {"test.pak": ["C:/mods/test.pak"]}
        assert loaded.layout_kind == "standard_pak_archive"
        assert loaded.target_root_hint == "paks"
        assert loaded.selected_entries == ["test.pak"]
        assert loaded.installed_archive_entries == ["test.pak"]
        assert loaded.layout_warnings == ["Support/metadata files were skipped during deployment planning."]

    def test_legacy_flat_metadata_fields_still_load(self, tmp_path):
        state_file = tmp_path / "app_state.json"
        state_file.write_text(json.dumps({
            "schema_version": 2,
            "mods": [{
                "mod_id": "flat_meta_mod",
                "display_name": "Flat Meta",
                "source_archive": "flat.zip",
                "targets": ["client"],
                "installed_files": ["C:/game/flat.pak"],
                "nexus_mod_id": "42",
                "nexus_file_id": "100",
                "version_tag": "2.0.0",
            }],
            "history": [],
        }), encoding="utf-8")

        mod = ManifestStore(tmp_path).get_mod("flat_meta_mod")
        assert mod is not None
        assert mod.metadata.nexus_mod_id == "42"
        assert mod.metadata.nexus_file_id == "100"
        assert mod.metadata.version_tag == "2.0.0"
        assert mod.layout_kind == ""
        assert mod.selected_entries == []

    def test_legacy_history_records_still_load_without_layout_metadata(self, tmp_path):
        state_file = tmp_path / "app_state.json"
        state_file.write_text(json.dumps({
            "schema_version": 2,
            "mods": [],
            "history": [{
                "mod_id": "old",
                "timestamp": "2026-04-01T00:00:00",
                "target": "client",
                "action": "install",
                "display_name": "Old Mod",
                "source_archive": "old.zip",
                "install_kind": "standard_mod",
                "notes": "Installed 1 files",
                "files": [{
                    "source_archive_path": "old.pak",
                    "dest_path": "C:/mods/old.pak",
                    "was_overwrite": False,
                }],
            }],
        }), encoding="utf-8")

        record = ManifestStore(tmp_path).list_history()[0]

        assert record.display_name == "Old Mod"
        assert record.layout_kind == ""
        assert record.selected_entries == []
        assert record.installed_archive_entries == []

    def test_deployment_record_layout_metadata_round_trip(self):
        record = DeploymentRecord(
            mod_id="mod",
            display_name="Mod",
            source_archive="mod.zip",
            archive_hash="abc123",
            selected_variant="Mod_x10_P.pak",
            selected_entries=["Mod_x10_P.pak"],
            installed_archive_entries=["Mod_x10_P.pak", "Mod_x10_P.utoc"],
            layout_kind="multi_variant_pak_archive",
            target_root_hint="paks",
            layout_warnings=["Support/metadata files were skipped."],
        )

        loaded = DeploymentRecord.from_dict(record.to_dict())

        assert loaded.archive_hash == "abc123"
        assert loaded.selected_variant == "Mod_x10_P.pak"
        assert loaded.selected_entries == ["Mod_x10_P.pak"]
        assert loaded.installed_archive_entries == ["Mod_x10_P.pak", "Mod_x10_P.utoc"]
        assert loaded.layout_kind == "multi_variant_pak_archive"
        assert loaded.target_root_hint == "paks"
        assert loaded.layout_warnings == ["Support/metadata files were skipped."]
