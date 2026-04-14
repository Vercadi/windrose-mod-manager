"""Main application window — assembles all tabs and services."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from .. import __app_name__, __version__
from ..core.backup_manager import BackupManager
from ..core.discovery import discover_all
from ..core.installer import Installer
from ..core.logging_service import setup_logging
from ..core.manifest_store import ManifestStore
from ..core.server_config_service import ServerConfigService
from ..models.app_paths import AppPaths
from ..utils.json_io import read_json, write_json
from ..utils.filesystem import ensure_dir
from .widgets.status_panel import StatusPanel

log = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = APP_DIR / "data"
DEFAULT_BACKUP_DIR = APP_DIR / "backups"
SETTINGS_FILE = DEFAULT_DATA_DIR / "settings.json"


class AppWindow(ctk.CTk):
    """Root application window."""

    def __init__(self):
        super().__init__()

        self.title(f"{__app_name__} v{__version__}")
        self.geometry("1100x750")
        self.minsize(900, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._init_services()
        self._build_ui()
        self._initial_load()

    # ---------------------------------------------------------- services

    def _init_services(self) -> None:
        ensure_dir(DEFAULT_DATA_DIR)
        ensure_dir(DEFAULT_BACKUP_DIR)

        setup_logging(log_dir=DEFAULT_DATA_DIR)

        self.paths = self._load_settings()

        if self.paths.data_dir is None:
            self.paths.data_dir = DEFAULT_DATA_DIR
        if self.paths.backup_dir is None:
            self.paths.backup_dir = DEFAULT_BACKUP_DIR

        self.backup = BackupManager(self.paths.backup_dir)
        self.manifest = ManifestStore(self.paths.data_dir)
        self.installer = Installer(self.backup)
        self.server_config_svc = ServerConfigService(self.backup)

        log.info("Services initialized")

    def _load_settings(self) -> AppPaths:
        if SETTINGS_FILE.is_file():
            data = read_json(SETTINGS_FILE)
            paths = AppPaths.from_dict(data.get("paths", {}))
            log.info("Loaded settings from %s", SETTINGS_FILE)
            return paths
        return AppPaths()

    def save_settings(self) -> None:
        ensure_dir(DEFAULT_DATA_DIR)
        write_json(SETTINGS_FILE, {"paths": self.paths.to_dict()})
        log.info("Settings saved to %s", SETTINGS_FILE)

    # ---------------------------------------------------------- UI

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self._tabview = ctk.CTkTabview(self)
        self._tabview.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))

        tab_mods = self._tabview.add("Mods")
        tab_installed = self._tabview.add("Installed")
        tab_server = self._tabview.add("Server")
        tab_backups = self._tabview.add("Backups")
        tab_settings = self._tabview.add("Settings")

        for tab in (tab_mods, tab_installed, tab_server, tab_backups, tab_settings):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        from .tabs.mods_tab import ModsTab
        from .tabs.installed_tab import InstalledTab
        from .tabs.server_tab import ServerTab
        from .tabs.backups_tab import BackupsTab
        from .tabs.settings_tab import SettingsTab

        self._mods_tab = ModsTab(tab_mods, app=self)
        self._mods_tab.grid(row=0, column=0, sticky="nsew")

        self._installed_tab = InstalledTab(tab_installed, app=self)
        self._installed_tab.grid(row=0, column=0, sticky="nsew")

        self._server_tab = ServerTab(tab_server, app=self)
        self._server_tab.grid(row=0, column=0, sticky="nsew")

        self._backups_tab = BackupsTab(tab_backups, app=self)
        self._backups_tab.grid(row=0, column=0, sticky="nsew")

        self._settings_tab = SettingsTab(tab_settings, app=self)
        self._settings_tab.grid(row=0, column=0, sticky="nsew")

        self._status = StatusPanel(self, height=140)
        self._status.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 8))

    # ---------------------------------------------------------- lifecycle

    def _initial_load(self) -> None:
        """Run first-time discovery if paths aren't configured."""
        if not self.paths.client_root:
            log.info("No client root configured — running auto-detection...")
            detected = discover_all()
            if detected.client_root:
                self.paths.client_root = detected.client_root
                log.info("Auto-detected client: %s", detected.client_root)
            if detected.server_root:
                self.paths.server_root = detected.server_root
                log.info("Auto-detected server: %s", detected.server_root)
            if detected.local_config:
                self.paths.local_config = detected.local_config
            if detected.local_save_root:
                self.paths.local_save_root = detected.local_save_root
            self.save_settings()

        self._installed_tab.refresh()
        self._backups_tab.refresh()

    # ---------------------------------------------------------- cross-tab helpers

    def refresh_installed_tab(self) -> None:
        self._installed_tab.refresh()

    def refresh_backups_tab(self) -> None:
        self._backups_tab.refresh()
