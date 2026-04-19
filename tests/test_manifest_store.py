"""Tests for windrose_deployer.core.manifest_store."""
import json
import pytest
from pathlib import Path

from windrose_deployer.core.manifest_store import ManifestStore
from windrose_deployer.models.metadata import ModMetadata
from windrose_deployer.models.mod_install import ModInstall


def _make_mod(mod_id: str = "test_mod", files: list[str] | None = None) -> ModInstall:
    return ModInstall(
        mod_id=mod_id,
        display_name=mod_id.replace("_", " ").title(),
        source_archive="test.zip",
        archive_hash="abc123",
        install_type="pak_only",
        selected_variant=None,
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
