from windrose_deployer.core.framework_detector import analyze_archive_framework, detect_framework_state
from windrose_deployer.models.archive_info import ArchiveEntry


def test_framework_detector_recognizes_ue4ss_runtime_archive():
    analysis = analyze_archive_framework(
        [
            ArchiveEntry(path="R5/Binaries/Win64/UE4SS.dll"),
            ArchiveEntry(path="R5/Binaries/Win64/UE4SS-settings.ini"),
            ArchiveEntry(path="ue4ss/Mods/shared/readme.txt"),
        ]
    )

    assert analysis.category == "framework_runtime"
    assert analysis.install_kind == "ue4ss_runtime"
    assert analysis.framework_name == "UE4SS Runtime"
    assert r"R5\Binaries\Win64" in analysis.likely_destinations


def test_framework_detector_recognizes_likely_ue4ss_dependent_mod():
    analysis = analyze_archive_framework(
        [
            ArchiveEntry(path="ue4ss/Mods/HarvestBoost/Scripts/main.lua"),
        ]
    )

    assert analysis.category == "framework_mod"
    assert analysis.install_kind == "ue4ss_mod"
    assert analysis.framework_name == "UE4SS"
    assert analysis.dependency_warnings


def test_framework_detector_recognizes_root_ue4ss_mod_archive():
    analysis = analyze_archive_framework(
        [
            ArchiveEntry(path="ToggleSprint/enabled.txt"),
            ArchiveEntry(path="ToggleSprint/Scripts/main.lua"),
        ]
    )

    assert analysis.category == "framework_mod"
    assert analysis.install_kind == "ue4ss_mod"
    assert analysis.detected_mod_name == "togglesprint"


def test_framework_detector_recognizes_rcon_mod_archive():
    analysis = analyze_archive_framework(
        [
            ArchiveEntry(path="WindroseRCON/enabled.txt"),
            ArchiveEntry(path="WindroseRCON/settings.ini"),
            ArchiveEntry(path="WindroseRCON/dlls/main.dll"),
        ]
    )

    assert analysis.install_kind == "rcon_mod"
    assert analysis.framework_name == "Windrose RCON"


def test_framework_detector_recognizes_windrose_rcon_version_dll_archive():
    analysis = analyze_archive_framework(
        [ArchiveEntry(path="version.dll")],
        archive_path="WindroseRCON-1-0.zip",
    )

    assert analysis.install_kind == "rcon_mod"
    assert r"R5\Binaries\Win64" in analysis.likely_destinations


def test_framework_detector_does_not_treat_generic_version_dll_as_rcon():
    analysis = analyze_archive_framework(
        [ArchiveEntry(path="version.dll")],
        archive_path="SomeOtherDllProxy.zip",
    )

    assert analysis.install_kind == "standard_mod"


def test_framework_detector_recognizes_windrose_plus_package():
    analysis = analyze_archive_framework(
        [
            ArchiveEntry(path="install.ps1"),
            ArchiveEntry(path="config/windrose_plus.default.ini"),
            ArchiveEntry(path="WindrosePlus/enabled.txt"),
            ArchiveEntry(path="WindrosePlus/Scripts/main.lua"),
        ]
    )

    assert analysis.install_kind == "windrose_plus"
    assert analysis.framework_name == "WindrosePlus"


def test_framework_detector_recognizes_windrose_plus_release_folder():
    analysis = analyze_archive_framework(
        [
            ArchiveEntry(path="windrose+/install.ps1"),
            ArchiveEntry(path="windrose+/UE4SS-settings.ini"),
            ArchiveEntry(path="windrose+/config/windrose_plus.default.ini"),
            ArchiveEntry(path="windrose+/WindrosePlus/enabled.txt"),
            ArchiveEntry(path="windrose+/WindrosePlus/Scripts/main.lua"),
        ]
    )

    assert analysis.install_kind == "windrose_plus"
    assert analysis.framework_name == "WindrosePlus"


def test_detect_framework_state_checks_runtime_markers(tmp_path):
    root = tmp_path / "Windrose"
    runtime_dir = root / "R5" / "Binaries" / "Win64"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "UE4SS.dll").write_text("x", encoding="utf-8")

    state = detect_framework_state(root)

    assert state["configured"] is True
    assert state["ue4ss_runtime"] is True
    assert state["ue4ss_partial"] is True


def test_detect_framework_state_does_not_count_mods_folder_as_runtime(tmp_path):
    root = tmp_path / "Windrose"
    mod_dir = root / "R5" / "Binaries" / "Win64" / "ue4ss" / "Mods" / "ToggleSprint" / "Scripts"
    mod_dir.mkdir(parents=True)
    (mod_dir / "main.lua").write_text("x", encoding="utf-8")

    state = detect_framework_state(root)

    assert state["ue4ss_runtime"] is False
    assert state["ue4ss_partial"] is True


def test_detect_framework_state_ignores_empty_rcon_folder(tmp_path):
    root = tmp_path / "WindroseServer"
    rcon_dir = root / "R5" / "Binaries" / "Win64" / "ue4ss" / "Mods" / "WindroseRCON"
    rcon_dir.mkdir(parents=True)

    state = detect_framework_state(root)

    assert state["rcon_mod"] is False
    assert state["rcon_configured"] is False


def test_detect_framework_state_checks_rcon_version_dll_and_generated_settings(tmp_path):
    root = tmp_path / "WindroseServer"
    win64 = root / "R5" / "Binaries" / "Win64"
    win64.mkdir(parents=True)
    (win64 / "version.dll").write_bytes(b"dll")
    (win64 / "windrosercon").mkdir()
    (win64 / "windrosercon" / "settings.ini").write_text("Port=27065\nPassword=secret\n", encoding="utf-8")

    state = detect_framework_state(root)

    assert state["rcon_mod"] is True
    assert state["rcon_configured"] is True
    assert state["rcon_missing_password"] is False


def test_detect_framework_state_marks_rcon_version_dll_without_settings_as_pending(tmp_path):
    root = tmp_path / "WindroseServer"
    win64 = root / "R5" / "Binaries" / "Win64"
    win64.mkdir(parents=True)
    (win64 / "version.dll").write_bytes(b"dll")

    state = detect_framework_state(root)

    assert state["rcon_mod"] is True
    assert state["rcon_configured"] is False
    assert state["rcon_missing_password"] is False


def test_detect_framework_state_checks_rcon_and_windrose_plus(tmp_path):
    root = tmp_path / "WindroseServer"
    mods = root / "R5" / "Binaries" / "Win64" / "ue4ss" / "Mods"
    (mods / "WindroseRCON").mkdir(parents=True)
    (mods / "WindroseRCON" / "settings.ini").write_text("Port=27065\nPassword=changeme\n", encoding="utf-8")
    (mods / "WindrosePlus").mkdir()
    (root / "StartWindrosePlusServer.bat").write_text("@echo off\n", encoding="utf-8")
    (root / "R5" / "Content" / "Paks").mkdir(parents=True)
    (root / "R5" / "Content" / "Paks" / "WindrosePlus_Multipliers_P.pak").write_bytes(b"x")

    state = detect_framework_state(root)

    assert state["rcon_mod"] is True
    assert state["rcon_configured"] is True
    assert state["rcon_missing_password"] is True
    assert state["windrose_plus"] is True
    assert state["windrose_plus_package"] is True
    assert state["windrose_plus_generated_paks"] is True
    assert state["windrose_plus_launch_wrapper"] is True
    assert state["windrose_plus_partial"] is False


def test_detect_framework_state_checks_windrose_plus_package_files(tmp_path):
    root = tmp_path / "WindroseServer"
    (root / "WindrosePlus").mkdir(parents=True)

    state = detect_framework_state(root)

    assert state["windrose_plus"] is False
    assert state["windrose_plus_package"] is True
    assert state["windrose_plus_partial"] is True
