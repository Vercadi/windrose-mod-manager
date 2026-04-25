from windrose_deployer.ui.tabs.mods_tab import ModsTab


def test_server_only_framework_presets_hide_client_targets():
    assert ModsTab._install_preset_allowed_for_kinds("local", ["rcon_mod"]) is True
    assert ModsTab._install_preset_allowed_for_kinds("dedicated", ["windrose_plus"]) is True
    assert ModsTab._install_preset_allowed_for_kinds("hosted", ["windrose_plus"]) is True
    assert ModsTab._install_preset_allowed_for_kinds("client", ["rcon_mod"]) is False
    assert ModsTab._install_preset_allowed_for_kinds("client_local", ["windrose_plus"]) is False
    assert ModsTab._install_preset_allowed_for_kinds("client_dedicated", ["windrose_plus"]) is False
