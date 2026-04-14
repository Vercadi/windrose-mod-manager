"""Main application window — assembles all tabs and services."""
from __future__ import annotations

import logging
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

import customtkinter as ctk

try:
    import tkinterdnd2
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

from .. import __app_name__, __version__
from ..core.backup_manager import BackupManager
from ..core.discovery import discover_all
from ..core.installer import Installer
from ..core.logging_service import setup_logging
from ..core.manifest_store import ManifestStore
from ..core.server_config_service import ServerConfigService
from ..core.update_checker import check_for_update
from ..core.world_config_service import WorldConfigService
from ..models.app_paths import AppPaths
from ..utils.json_io import read_json, write_json
from ..utils.filesystem import ensure_dir
from .widgets.status_panel import StatusPanel

log = logging.getLogger(__name__)


def _resolve_app_dirs() -> tuple[Path, Path, Path]:
    """Determine data, backup, and settings paths.

    When running from source, use directories next to the repo root.
    When frozen (PyInstaller), use %LOCALAPPDATA%/WindroseModDeployer so we
    never try to write inside the packaged exe folder.
    """
    import os
    import sys

    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WindroseModDeployer"
    else:
        base = Path(__file__).resolve().parent.parent.parent

    data_dir = base / "data"
    backup_dir = base / "backups"
    settings_file = data_dir / "settings.json"
    return data_dir, backup_dir, settings_file


DEFAULT_DATA_DIR, DEFAULT_BACKUP_DIR, SETTINGS_FILE = _resolve_app_dirs()


class AppWindow(ctk.CTk):
    """Root application window with optional drag-and-drop support."""

    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()

        # Inject tkdnd so all widgets get drop_target_register / dnd_bind
        self._dnd_enabled = False
        if _DND_AVAILABLE:
            try:
                tkinterdnd2.TkinterDnD._require(self)
                self._dnd_enabled = True
                log.info("Drag-and-drop enabled via tkdnd")
            except Exception as exc:
                log.warning("tkdnd init failed, drag-and-drop disabled: %s", exc)

        self.title(f"{__app_name__} v{__version__}")
        self.geometry("1100x750")
        self.minsize(900, 600)

        self._set_icon()

        self._init_services()
        self._build_ui()
        self._initial_load()

    def _set_icon(self) -> None:
        """Set the window/taskbar icon from assets/.

        CustomTkinter 5.x overrides iconbitmap after ~200ms with its own
        default icon.  We schedule our icon calls at 300ms to run after
        that override, and keep a reference to the PhotoImage to prevent GC.
        """
        import sys
        from tkinter import PhotoImage

        if getattr(sys, "frozen", False):
            assets = Path(sys._MEIPASS) / "assets"
        else:
            assets = Path(__file__).resolve().parent.parent.parent / "assets"

        ico_path = assets / "icon.ico"
        png_path = assets / "icon_256.png"

        def _apply_icon() -> None:
            try:
                if ico_path.is_file():
                    self.iconbitmap(str(ico_path))
                if png_path.is_file():
                    photo = PhotoImage(file=str(png_path))
                    self.wm_iconphoto(True, photo)
                    self._icon_photo = photo
            except Exception as exc:
                log.debug("Could not set icon: %s", exc)

        # Apply immediately (may get overridden by CTk)
        _apply_icon()
        # Re-apply after CTk's 200ms default-icon override
        self.after(300, _apply_icon)

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
        self.world_config_svc = WorldConfigService(self.backup)

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
        # row 0: update banner (hidden by default)
        # row 1: tab view (main)
        # row 2: launch bar
        # row 3: status panel
        self.grid_rowconfigure(1, weight=1)

        self._build_update_banner()

        self._tabview = ctk.CTkTabview(self)
        self._tabview.grid(row=1, column=0, sticky="nsew", padx=8, pady=(8, 0))

        tab_mods = self._tabview.add("Mods")
        tab_installed = self._tabview.add("Installed")
        tab_server = self._tabview.add("Server")
        tab_backups = self._tabview.add("Backups")
        tab_settings = self._tabview.add("Settings")
        tab_about = self._tabview.add("About")

        for tab in (tab_mods, tab_installed, tab_server, tab_backups,
                     tab_settings, tab_about):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        from .tabs.mods_tab import ModsTab
        from .tabs.installed_tab import InstalledTab
        from .tabs.server_tab import ServerTab
        from .tabs.backups_tab import BackupsTab
        from .tabs.settings_tab import SettingsTab
        from .tabs.about_tab import AboutTab

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

        self._about_tab = AboutTab(tab_about, app=self)
        self._about_tab.grid(row=0, column=0, sticky="nsew")

        self._build_launch_bar()

        self._status = StatusPanel(self, height=140)
        self._status.grid(row=3, column=0, sticky="ew", padx=8, pady=(4, 8))

    # ---------------------------------------------------------- update banner

    def _build_update_banner(self) -> None:
        """Hidden banner shown when a newer release exists on GitHub."""
        self._update_frame = ctk.CTkFrame(self, fg_color="#1a5276", height=36,
                                          corner_radius=0)
        self._update_label = ctk.CTkLabel(
            self._update_frame, text="", font=ctk.CTkFont(size=12),
            text_color="#d4efff",
        )
        self._update_label.pack(side="left", padx=12, pady=6)
        self._update_btn = ctk.CTkButton(
            self._update_frame, text="Download", width=90,
            fg_color="#2980b9", hover_color="#2471a3",
            command=self._on_open_update,
        )
        self._update_btn.pack(side="right", padx=12, pady=6)
        self._update_url: str = ""

    def _on_open_update(self) -> None:
        if self._update_url:
            webbrowser.open(self._update_url)

    def _show_update_banner(self, new_version: str, url: str) -> None:
        """Called from the background update-check thread."""
        def _show():
            self._update_url = url
            self._update_label.configure(
                text=f"A new version is available: v{new_version}  (you have v{__version__})")
            self._update_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.after(0, _show)

    # ---------------------------------------------------------- launch bar

    def _build_launch_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent", height=40)
        bar.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 0))
        bar.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        self._launch_game_btn = ctk.CTkButton(
            inner, text="▶  Start Game", width=140,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_start_game,
        )
        self._launch_game_btn.pack(side="left", padx=4)

        self._launch_server_btn = ctk.CTkButton(
            inner, text="▶  Start Server", width=140,
            fg_color="#555555", hover_color="#666666",
            command=self._on_start_server,
        )
        self._launch_server_btn.pack(side="left", padx=4)

        badge_frame = ctk.CTkFrame(bar, fg_color="transparent")
        badge_frame.place(relx=1.0, rely=0.5, anchor="e")
        self._mod_count_label = ctk.CTkLabel(
            badge_frame, text="",
            font=ctk.CTkFont(size=11), text_color="#95a5a6",
        )
        self._mod_count_label.pack(padx=8)

    def _on_start_game(self) -> None:
        exe = self.paths.client_root / "Windrose.exe" if self.paths.client_root else None
        if exe and exe.is_file():
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
            log.info("Launched game: %s", exe)
        else:
            from tkinter import messagebox
            messagebox.showerror("Not Found",
                                 "Windrose.exe not found. Check client path in Settings.")

    def _on_start_server(self) -> None:
        if self.paths.server_root:
            bat = self.paths.server_root / "StartServerForeground.bat"
            exe = self.paths.server_root / "WindroseServer.exe"
            target = bat if bat.is_file() else exe
        else:
            target = None

        if target and target.is_file():
            subprocess.Popen([str(target)], cwd=str(target.parent))
            log.info("Launched server: %s", target)
        else:
            from tkinter import messagebox
            messagebox.showerror("Not Found",
                                 "Server executable not found. Check server path in Settings.")

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
        self._update_mod_badge()

        check_for_update(__version__, self._show_update_banner)

    # ---------------------------------------------------------- cross-tab helpers

    def refresh_installed_tab(self) -> None:
        self._installed_tab.refresh()
        self._update_mod_badge()

    def refresh_backups_tab(self) -> None:
        self._backups_tab.refresh()

    def _update_mod_badge(self) -> None:
        count = len(self.manifest.list_mods())
        if count:
            self._mod_count_label.configure(text=f"{count} mod{'s' if count != 1 else ''} installed")
        else:
            self._mod_count_label.configure(text="")
