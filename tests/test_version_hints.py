from windrose_deployer.core.version_hints import possible_update_hint_for_archive
from windrose_deployer.models.metadata import ModMetadata
from windrose_deployer.models.mod_install import ModInstall


def test_version_hint_uses_matching_nexus_metadata():
    entry = {
        "path": "Stacks-new.zip",
        "name": "Stacks-new",
        "metadata": {
            "nexus_mod_id": "28",
            "version_tag": "1.0.2",
        },
    }
    installed = [
        ModInstall(
            mod_id="a",
            display_name="Stacks",
            source_archive="Stacks-old.zip",
            targets=["client"],
            installed_files=["C:/mods/Stacks.pak"],
            metadata=ModMetadata(nexus_mod_id="28", version_tag="1.0.1"),
        )
    ]

    hint = possible_update_hint_for_archive(entry, installed)
    assert "Possible update available" in hint


def test_version_hint_falls_back_to_family_name():
    entry = {
        "path": "Expanded-Horizons-v2.4.zip",
        "name": "Expanded-Horizons-v2.4",
        "metadata": {},
    }
    installed = [
        ModInstall(
            mod_id="a",
            display_name="Expanded Horizons",
            source_archive="Expanded-Horizons-v2.3.zip",
            targets=["client"],
            installed_files=["C:/mods/EH.pak"],
        )
    ]

    hint = possible_update_hint_for_archive(entry, installed)
    assert "supersede" in hint
