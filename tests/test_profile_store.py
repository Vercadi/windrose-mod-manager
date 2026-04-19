from windrose_deployer.core.profile_store import ProfileStore
from windrose_deployer.models.metadata import ModMetadata
from windrose_deployer.models.profile import Profile, ProfileEntry


def test_profile_store_missing_file_is_clean(tmp_path):
    store = ProfileStore(tmp_path / "data")
    assert store.list_profiles() == []


def test_profile_store_round_trips_entries_and_snapshots(tmp_path):
    store = ProfileStore(tmp_path / "data")
    profile = Profile.new("Smoke")
    profile.notes = "Test profile"
    profile.entries.append(
        ProfileEntry(
            display_name="More Stacks",
            source_archive="MoreStacks.zip",
            targets=["client", "server"],
            selected_variant="MoreStacks_100x_P.pak",
            component_entries=["MoreStacks_100x_P.pak"],
            metadata=ModMetadata(
                nexus_mod_id="28",
                nexus_file_id="1776195732",
                version_tag="1.0.1",
            ),
        )
    )
    profile.server_settings_snapshot = {"ServerName": "Smoke Server"}
    profile.world_settings_snapshot = {"WorldName": "Smoke World"}

    store.upsert(profile)

    loaded = ProfileStore(tmp_path / "data").get_profile(profile.profile_id)
    assert loaded is not None
    assert loaded.name == "Smoke"
    assert loaded.entries[0].metadata.nexus_mod_id == "28"
    assert loaded.server_settings_snapshot["ServerName"] == "Smoke Server"
    assert loaded.world_settings_snapshot["WorldName"] == "Smoke World"


def test_profile_store_skips_corrupt_entries(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "profiles.json").write_text(
        '{"profiles":[{"bad":"entry"},{"profile_id":"ok","name":"Valid","entries":[]}]}',
        encoding="utf-8",
    )

    store = ProfileStore(data_dir)
    names = [profile.name for profile in store.list_profiles()]
    assert names == ["Valid"]
