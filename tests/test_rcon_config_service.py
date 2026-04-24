from windrose_deployer.core.rcon_config_service import RconConfigService, RconSettings, parse_rcon_settings


def test_parse_rcon_settings_reads_simple_key_value_file():
    settings = parse_rcon_settings(
        "# WindroseRCON Configuration\n"
        "Port=27065\n"
        "\n"
        "Password=secret\n",
        source_path="settings.ini",
    )

    assert settings.enabled is True
    assert settings.port == 27065
    assert settings.password == "secret"
    assert settings.source_path == "settings.ini"


def test_rcon_settings_serializes_simple_key_value_file():
    text = RconSettings(port=1234, password="pw").to_text()

    assert "Port=1234" in text
    assert "Password=pw" in text


def test_local_settings_path_uses_ue4ss_mod_location(tmp_path):
    path = RconConfigService.local_settings_path(tmp_path)

    assert path is not None
    assert path.relative_to(tmp_path).as_posix() == "R5/Binaries/Win64/ue4ss/Mods/WindroseRCON/settings.ini"
