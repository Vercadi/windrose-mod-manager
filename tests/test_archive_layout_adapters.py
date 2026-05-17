from pathlib import Path
import zipfile

from windrose_deployer.core.archive_inspector import inspect_archive
from windrose_deployer.core.archive_layout import ArchiveLayoutKind, classify_archive_layout


def _inspect_zip(tmp_path: Path, name: str, entries: dict[str, str]) -> object:
    archive = tmp_path / name
    with zipfile.ZipFile(archive, "w") as zf:
        for path, data in entries.items():
            zf.writestr(path, data)
    return inspect_archive(archive)


def test_standard_pak_archive_groups_pak_and_companions(tmp_path: Path):
    info = _inspect_zip(
        tmp_path,
        "standard.zip",
        {
            "BetterWind_P.pak": "pak",
            "BetterWind_P.utoc": "utoc",
            "BetterWind_P.ucas": "ucas",
            "README.md": "readme",
        },
    )

    layout = classify_archive_layout(info)

    assert layout.kind == ArchiveLayoutKind.STANDARD_PAK
    assert layout.target_root_hint == "paks"
    assert not layout.requires_user_choice
    assert set(layout.installable_paths) == {
        "BetterWind_P.pak",
        "BetterWind_P.utoc",
        "BetterWind_P.ucas",
    }
    assert [group.name for group in layout.component_groups] == ["BetterWind_P"]
    assert [entry.path for entry in layout.support_files] == ["README.md"]


def test_multi_pak_bundle_is_not_treated_as_variant_choice(tmp_path: Path):
    info = _inspect_zip(
        tmp_path,
        "bundle.zip",
        {
            "Inventory_P.pak": "pak",
            "Ships_P.pak": "pak",
        },
    )

    layout = classify_archive_layout(info)

    assert layout.kind == ArchiveLayoutKind.MULTI_PAK_BUNDLE
    assert not layout.requires_user_choice
    assert set(layout.installable_paths) == {"Inventory_P.pak", "Ships_P.pak"}
    assert {group.name for group in layout.component_groups} == {"Inventory_P", "Ships_P"}


def test_multi_variant_pak_archive_requires_choice(tmp_path: Path):
    info = _inspect_zip(
        tmp_path,
        "variants.zip",
        {
            "MoreStacks_x10_P.pak": "pak",
            "MoreStacks_x10_P.utoc": "utoc",
            "MoreStacks_x20_P.pak": "pak",
            "MoreStacks_x20_P.utoc": "utoc",
        },
    )

    layout = classify_archive_layout(info)

    assert layout.kind == ArchiveLayoutKind.MULTI_VARIANT_PAK
    assert layout.requires_user_choice
    assert len(layout.variant_groups) == 1
    assert set(layout.installable_paths) == {
        "MoreStacks_x10_P.pak",
        "MoreStacks_x10_P.utoc",
        "MoreStacks_x20_P.pak",
        "MoreStacks_x20_P.utoc",
    }
    assert any("choose one variant" in warning.lower() for warning in layout.warnings)


def test_ue4ss_mod_archive_maps_mod_payload(tmp_path: Path):
    info = _inspect_zip(
        tmp_path,
        "ToggleSprint.zip",
        {
            "ToggleSprint/enabled.txt": "1",
            "ToggleSprint/Scripts/main.lua": "print('toggle')",
            "README.txt": "readme",
        },
    )

    layout = classify_archive_layout(info)

    assert layout.kind == ArchiveLayoutKind.UE4SS_MOD
    assert layout.target_root_hint == r"R5\Binaries\Win64\ue4ss\Mods"
    assert set(layout.installable_paths) == {
        "ToggleSprint/enabled.txt",
        "ToggleSprint/Scripts/main.lua",
    }
    assert layout.component_groups[0].name == "ToggleSprint"


def test_ue4ss_runtime_archive_maps_runtime_payload(tmp_path: Path):
    info = _inspect_zip(
        tmp_path,
        "UE4SS.zip",
        {
            "UE4SS/dwmapi.dll": "dll",
            "UE4SS/ue4ss/UE4SS.dll": "dll",
            "UE4SS/ue4ss/UE4SS-settings.ini": "ini",
            "UE4SS/readme.txt": "readme",
        },
    )

    layout = classify_archive_layout(info)

    assert layout.kind == ArchiveLayoutKind.UE4SS_RUNTIME
    assert layout.target_root_hint == r"R5\Binaries\Win64"
    assert set(layout.installable_paths) == {
        "UE4SS/dwmapi.dll",
        "UE4SS/ue4ss/UE4SS.dll",
        "UE4SS/ue4ss/UE4SS-settings.ini",
    }


def test_ue4ss_shim_runtime_archive_is_called_out(tmp_path: Path):
    info = _inspect_zip(
        tmp_path,
        "UE4SS-ShimLoader.zip",
        {
            "dwmapi.dll": "dll",
            "README.md": "readme",
        },
    )

    layout = classify_archive_layout(info)

    assert layout.kind == ArchiveLayoutKind.UE4SS_SHIM_RUNTIME
    assert layout.installable_paths == ("dwmapi.dll",)
    assert any("shim" in warning.lower() for warning in layout.warnings)


def test_config_only_archive_separates_config_from_installables(tmp_path: Path):
    info = _inspect_zip(
        tmp_path,
        "configs.zip",
        {
            "ServerDescription.json": "{}",
            "settings.cfg": "value=true",
            "README.md": "readme",
        },
    )

    layout = classify_archive_layout(info)

    assert layout.kind == ArchiveLayoutKind.CONFIG_ONLY
    assert layout.installable_paths == tuple()
    assert {entry.path for entry in layout.config_files} == {"ServerDescription.json", "settings.cfg"}
    assert layout.requires_user_choice


def test_mixed_archive_reports_manual_review_warning(tmp_path: Path):
    info = _inspect_zip(
        tmp_path,
        "mixed.zip",
        {
            "BetterWind_P.pak": "pak",
            "extras/helper.exe": "tool",
            "Config/settings.ini": "value=true",
        },
    )

    layout = classify_archive_layout(info)

    assert layout.kind == ArchiveLayoutKind.MIXED
    assert layout.requires_user_choice
    assert any("mixed archive layout" in warning.lower() for warning in layout.warnings)
    assert "extras/helper.exe" in layout.installable_paths
    assert [entry.path for entry in layout.config_files] == ["Config/settings.ini"]


def test_metadata_only_files_are_not_installable(tmp_path: Path):
    info = _inspect_zip(
        tmp_path,
        "metadata.zip",
        {
            "manifest.json": "{}",
            "README.md": "readme",
            "icon.png": "png",
        },
    )

    layout = classify_archive_layout(info)

    assert layout.kind == ArchiveLayoutKind.UNKNOWN
    assert layout.installable_paths == tuple()
    assert {entry.path for entry in layout.support_files} == {"manifest.json", "README.md", "icon.png"}
