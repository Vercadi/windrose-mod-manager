"""Tests for UI preference normalization and confirmation behavior."""

from types import SimpleNamespace

from windrose_deployer.models.app_preferences import AppPreferences
from windrose_deployer.ui.app_window import AppWindow
from windrose_deployer.ui.tabs.settings_tab import SettingsTab
from windrose_deployer.ui.ui_tokens import ui_tokens_for_size


class TestAppPreferences:
    def test_from_dict_normalizes_unknown_values(self):
        prefs = AppPreferences.from_dict(
            {
                "ui_size": "huge",
                "confirmation_mode": "sometimes",
            }
        )

        assert prefs.ui_size == "default"
        assert prefs.confirmation_mode == "destructive_only"

    def test_to_dict_uses_normalized_values(self):
        prefs = AppPreferences(ui_size="compact", confirmation_mode="reduced")

        assert prefs.to_dict() == {
            "ui_size": "compact",
            "confirmation_mode": "reduced",
        }


class TestUiTokens:
    def test_large_mode_is_roomier_than_compact(self):
        compact = ui_tokens_for_size("compact")
        large = ui_tokens_for_size("large")

        assert large.scale > compact.scale
        assert large.body > compact.body
        assert large.button_height > compact.button_height
        assert large.compact_name_len > compact.compact_name_len


class TestConfirmationBehavior:
    def test_always_mode_confirms_routine_actions(self):
        app = SimpleNamespace(preferences=SimpleNamespace(confirmation_mode="always"))

        assert AppWindow.should_confirm(app, "routine") is True
        assert AppWindow.should_confirm(app, "bulk") is True

    def test_destructive_only_mode_skips_routine_but_keeps_bulk(self):
        app = SimpleNamespace(preferences=SimpleNamespace(confirmation_mode="destructive_only"))

        assert AppWindow.should_confirm(app, "routine") is False
        assert AppWindow.should_confirm(app, "bulk") is True
        assert AppWindow.should_confirm(app, "destructive") is True

    def test_reduced_mode_keeps_high_risk_categories(self):
        app = SimpleNamespace(preferences=SimpleNamespace(confirmation_mode="reduced"))

        assert AppWindow.should_confirm(app, "routine") is False
        assert AppWindow.should_confirm(app, "hosted") is True
        assert AppWindow.should_confirm(app, "variant") is True


class TestSettingsBehaviorLabels:
    def test_ui_size_values_are_exposed_as_user_labels(self):
        assert SettingsTab._ui_size_label("compact") == "Compact"
        assert SettingsTab._ui_size_label("default") == "Default"
        assert SettingsTab._ui_size_label("large") == "Large"

    def test_confirmation_values_are_exposed_as_user_labels(self):
        assert SettingsTab._confirmation_mode_label("always") == "Always Confirm"
        assert SettingsTab._confirmation_mode_label("destructive_only") == "Destructive Actions Only"
        assert SettingsTab._confirmation_mode_label("reduced") == "Reduced Confirmations"
