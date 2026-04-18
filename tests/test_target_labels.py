"""Tests for shared install-target display semantics."""

from windrose_deployer.core.recovery_service import RecoveryService
from windrose_deployer.core.server_sync_service import ServerSyncService
from windrose_deployer.models.mod_install import (
    InstallTarget,
    expand_target_values,
    install_target_label,
    summarize_target_values,
    target_value_label,
)


def test_target_value_label_uses_local_server_wording():
    assert target_value_label("server") == "Local Server"
    assert install_target_label(InstallTarget.BOTH) == "Client + Local Server"


def test_expand_and_summarize_target_values_handle_both():
    assert expand_target_values(["both"]) == {"client", "server"}
    assert summarize_target_values(["both"]) == "Client + Local Server"
    assert summarize_target_values(["client", "dedicated_server"]) == "Client + Dedicated Server"


def test_recovery_titles_distinguish_local_and_dedicated_server_saves():
    assert RecoveryService._history_title("save_server_config", "Example", "server") == "Saved Local Server Settings"
    assert RecoveryService._history_title("save_server_config", "Example", "dedicated_server") == "Saved Dedicated Server Settings"
    assert RecoveryService._history_title("save_world_config", "Example", "server") == "Saved Local World Settings"


def test_server_sync_uses_local_server_label():
    assert ServerSyncService._target_label("server") == "local server"
