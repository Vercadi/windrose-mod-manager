from windrose_deployer.core.profile_service import ProfileService
from windrose_deployer.models.metadata import ModMetadata
from windrose_deployer.models.mod_install import ModInstall


def _mod(
    *,
    name: str,
    archive: str,
    targets: list[str],
    variant: str = "",
    components: dict[str, list[str]] | None = None,
) -> ModInstall:
    return ModInstall(
        mod_id=name.lower().replace(" ", "_"),
        display_name=name,
        source_archive=archive,
        targets=targets,
        selected_variant=variant or None,
        installed_files=[path for paths in (components or {"main.pak": ["C:/mods/main.pak"]}).values() for path in paths],
        component_map=components or {"main.pak": ["C:/mods/main.pak"]},
        metadata=ModMetadata(version_tag="1.0.0"),
    )


def test_capture_current_state_preserves_targets_variant_and_metadata():
    profile = ProfileService().capture_current_state(
        name="Smoke",
        mods=[
            _mod(
                name="Stacks",
                archive="Stacks.zip",
                targets=["client"],
                variant="Stacks_x10.pak",
                components={"Stacks_x10.pak": ["C:/mods/Stacks_x10.pak"]},
            )
        ],
    )

    assert profile.entries[0].targets == ["client"]
    assert profile.entries[0].selected_variant == "Stacks_x10.pak"
    assert profile.entries[0].metadata.version_tag == "1.0.0"


def test_compare_identifies_match_install_uninstall_and_missing_archive(tmp_path):
    existing = [
        _mod(name="Keep", archive=str(tmp_path / "Keep.zip"), targets=["client"]),
        _mod(name="Remove", archive=str(tmp_path / "Remove.zip"), targets=["server"]),
    ]
    keep_archive = tmp_path / "Keep.zip"
    keep_archive.write_text("zip", encoding="utf-8")
    desired_missing = tmp_path / "Missing.zip"

    service = ProfileService()
    profile = service.capture_current_state(name="Smoke", mods=[existing[0]])
    profile.entries.append(
        profile.entries[0].__class__(
            display_name="Need Install",
            source_archive=str(desired_missing),
            targets=["dedicated_server"],
        )
    )

    comparison = service.compare(profile, existing)

    assert [entry.display_name for entry in comparison.matching] == ["Keep"]
    assert [mod.display_name for mod in comparison.to_uninstall] == ["Remove"]
    assert [entry.display_name for entry in comparison.missing_archives] == ["Need Install"]
