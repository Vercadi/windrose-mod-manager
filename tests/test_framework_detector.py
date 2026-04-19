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
    assert analysis.framework_name == "UE4SS Runtime"
    assert r"R5\Binaries\Win64" in analysis.likely_destinations


def test_framework_detector_recognizes_likely_ue4ss_dependent_mod():
    analysis = analyze_archive_framework(
        [
            ArchiveEntry(path="ue4ss/Mods/HarvestBoost/Scripts/main.lua"),
        ]
    )

    assert analysis.category == "framework_mod"
    assert analysis.framework_name == "UE4SS"
    assert analysis.dependency_warnings


def test_detect_framework_state_checks_runtime_markers(tmp_path):
    root = tmp_path / "Windrose"
    runtime_dir = root / "R5" / "Binaries" / "Win64"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "UE4SS.dll").write_text("x", encoding="utf-8")

    state = detect_framework_state(root)

    assert state["configured"] is True
    assert state["ue4ss_runtime"] is True
