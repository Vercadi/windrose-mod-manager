"""Main application window — assembles all tabs and services."""
from __future__ import annotations

import logging
import queue
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

try:
    import tkinterdnd2
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

from .. import __app_name__, __version__
from ..core.backup_manager import BackupManager
from ..core.discovery import discover_all, reconcile_paths
from ..core.integrity_service import IntegrityService
from ..core.framework_state_service import FrameworkStateService
from ..core.framework_config_service import FrameworkConfigService
from ..core.installer import Installer
from ..core.logging_service import setup_logging
from ..core.manifest_store import ManifestStore
from ..core.profile_store import ProfileStore
from ..core.profile_service import ProfileService
from ..core.recovery_service import RecoveryService
from ..core.remote_deployer import RemoteDeploymentService
from ..core.restore_vanilla_service import RestoreVanillaPlan, RestoreVanillaService
from ..core.rcon_config_service import RconConfigService
from ..core.remote_config_service import RemoteConfigService
from ..core.remote_profile_store import RemoteProfileStore
from ..core.server_config_service import ServerConfigService
from ..core.server_sync_service import ServerSyncService
from ..core.support_diagnostics import SupportDiagnosticsService
from ..core.update_checker import ReleaseInfo, check_for_update, download_release_asset
from ..core.world_config_service import WorldConfigService
from ..models.app_preferences import AppPreferences
from ..models.app_paths import AppPaths
from ..models.deployment_record import DeploymentRecord
from ..utils.json_io import read_json, write_json
from ..utils.filesystem import ensure_dir
from .ui_tokens import UiTokens, ui_tokens_for_size
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
        self._startup_started_at = time.perf_counter()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self._first_run = not SETTINGS_FILE.is_file()
        super().__init__()
        self._ui_call_queue: queue.Queue = queue.Queue()
        self._process_names_cache: set[str] = set()
        self._process_names_cache_at = 0.0
        self._manifest_drift_warnings: list[str] = []
        self._last_hosted_diagnostics = ""

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
        self.geometry("1280x860")
        self.minsize(1040, 700)

        self._set_icon()

        stage_started = time.perf_counter()
        self._init_services()
        self._log_startup_timing("_init_services", stage_started)
        stage_started = time.perf_counter()
        self._init_ui_preferences()
        self._log_startup_timing("_init_ui_preferences", stage_started)
        stage_started = time.perf_counter()
        self._build_ui()
        self._log_startup_timing("_build_ui", stage_started)
        stage_started = time.perf_counter()
        self._initial_load()
        self._log_startup_timing("_initial_load", stage_started)
        self.after_idle(self._log_startup_ready)

    def _log_startup_timing(self, stage: str, started_at: float) -> None:
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        total_ms = (time.perf_counter() - self._startup_started_at) * 1000.0
        log.info("Startup timing | %s: %.1f ms (total %.1f ms)", stage, elapsed_ms, total_ms)

    def _log_startup_ready(self) -> None:
        total_ms = (time.perf_counter() - self._startup_started_at) * 1000.0
        log.info("Startup timing | window_ready: %.1f ms total", total_ms)

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
        stage_started = time.perf_counter()
        ensure_dir(DEFAULT_DATA_DIR)
        ensure_dir(DEFAULT_BACKUP_DIR)

        setup_logging(log_dir=DEFAULT_DATA_DIR)
        self._log_startup_timing("_init_services.setup_logging", stage_started)

        stage_started = time.perf_counter()
        self.paths = self._load_settings()
        self._log_startup_timing("_init_services.load_settings", stage_started)

        if self.paths.data_dir is None:
            self.paths.data_dir = DEFAULT_DATA_DIR
        if self.paths.backup_dir is None:
            self.paths.backup_dir = DEFAULT_BACKUP_DIR
        stage_started = time.perf_counter()
        reconciled_paths, changed = reconcile_paths(self.paths)
        self._log_startup_timing("_init_services.reconcile_paths", stage_started)
        if changed:
            old_server_root = self.paths.server_root
            old_dedicated_server_root = self.paths.dedicated_server_root
            old_save_root = self.paths.local_save_root
            self.paths = reconciled_paths
            self.save_settings()
            log.info(
                "Reconciled saved paths. Local server root: %s -> %s | Dedicated server root: %s -> %s | Save root: %s -> %s",
                old_server_root,
                self.paths.server_root,
                old_dedicated_server_root,
                self.paths.dedicated_server_root,
                old_save_root,
                self.paths.local_save_root,
            )
        else:
            self.paths = reconciled_paths

        stage_started = time.perf_counter()
        self._rebind_backup_services()
        self._log_startup_timing("_init_services.rebind_backup_services", stage_started)
        stage_started = time.perf_counter()
        self.manifest = ManifestStore(self.paths.data_dir)
        self.remote_profiles = RemoteProfileStore(self.paths.data_dir)
        self.profiles = ProfileStore(self.paths.data_dir)
        self.profile_service = ProfileService()
        self.remote_deployer = RemoteDeploymentService()
        self.framework_state = FrameworkStateService()
        self.framework_config = FrameworkConfigService(self.backup)
        self.rcon_config_svc = RconConfigService(self.backup)
        self.restore_vanilla = RestoreVanillaService(self.paths, self.manifest, self.installer, self.backup)
        self.remote_config_svc = RemoteConfigService(self.backup, self.remote_profiles)
        self.recovery = RecoveryService(self.manifest, self.backup)
        self.server_sync = ServerSyncService()
        self.support_diagnostics = SupportDiagnosticsService()
        self._log_startup_timing("_init_services.service_wiring", stage_started)

        log.info("Services initialized")

    def _rebind_backup_services(self) -> None:
        """Recreate services that are bound to the current backup root."""
        backup_dir = self.paths.backup_dir or DEFAULT_BACKUP_DIR
        ensure_dir(backup_dir)
        self.backup = BackupManager(backup_dir)
        self.installer = Installer(self.backup)
        self.server_config_svc = ServerConfigService(self.backup)
        self.world_config_svc = WorldConfigService(self.backup)
        self.framework_config = FrameworkConfigService(self.backup)
        self.rcon_config_svc = RconConfigService(self.backup)
        self.integrity = IntegrityService(self.paths, self.backup)
        if "remote_profiles" in self.__dict__:
            self.remote_config_svc = RemoteConfigService(self.backup, self.remote_profiles)
        if "manifest" in self.__dict__:
            self.recovery = RecoveryService(self.manifest, self.backup)
            self.restore_vanilla = RestoreVanillaService(self.paths, self.manifest, self.installer, self.backup)
        log.info("Rebound backup-backed services to %s", backup_dir)

    def _load_settings(self) -> AppPaths:
        if SETTINGS_FILE.is_file():
            data = read_json(SETTINGS_FILE)
            self.preferences = AppPreferences.from_dict(data.get("preferences", {}))
            paths = AppPaths.from_dict(data.get("paths", {}))
            log.info("Loaded settings from %s", SETTINGS_FILE)
            return paths
        self.preferences = AppPreferences()
        return AppPaths()

    def save_settings(self) -> None:
        ensure_dir(DEFAULT_DATA_DIR)
        write_json(
            SETTINGS_FILE,
            {
                "paths": self.paths.to_dict(),
                "preferences": self.preferences.to_dict(),
            },
        )
        log.info("Settings saved to %s", SETTINGS_FILE)

    def _init_ui_preferences(self) -> None:
        self._ui_tokens = ui_tokens_for_size(self.preferences.ui_size)
        self._fonts = {
            "page_title": ctk.CTkFont(size=self._ui_tokens.page_title, weight="bold"),
            "title": ctk.CTkFont(size=self._ui_tokens.title, weight="bold"),
            "detail_title": ctk.CTkFont(size=self._ui_tokens.detail_title, weight="bold"),
            "section_title": ctk.CTkFont(size=self._ui_tokens.section_title, weight="bold"),
            "card_title": ctk.CTkFont(size=self._ui_tokens.card_title, weight="bold"),
            "row_title": ctk.CTkFont(size=self._ui_tokens.row_title, weight="bold"),
            "body": ctk.CTkFont(size=self._ui_tokens.body),
            "small": ctk.CTkFont(size=self._ui_tokens.small),
            "tiny": ctk.CTkFont(size=self._ui_tokens.tiny),
            "mono": ctk.CTkFont(family="Consolas", size=self._ui_tokens.mono),
            "mono_small": ctk.CTkFont(family="Consolas", size=self._ui_tokens.mono_small),
        }
        self._apply_ui_preferences()

    def _apply_ui_preferences(self) -> None:
        self._ui_tokens = ui_tokens_for_size(self.preferences.ui_size)
        # UI Size is intended to change readability and density inside the app,
        # not to resize the outer window itself.
        ctk.set_widget_scaling(self._ui_tokens.scale)
        if hasattr(self, "_fonts"):
            self._fonts["page_title"].configure(size=self._ui_tokens.page_title)
            self._fonts["title"].configure(size=self._ui_tokens.title)
            self._fonts["detail_title"].configure(size=self._ui_tokens.detail_title)
            self._fonts["section_title"].configure(size=self._ui_tokens.section_title)
            self._fonts["card_title"].configure(size=self._ui_tokens.card_title)
            self._fonts["row_title"].configure(size=self._ui_tokens.row_title)
            self._fonts["body"].configure(size=self._ui_tokens.body)
            self._fonts["small"].configure(size=self._ui_tokens.small)
            self._fonts["tiny"].configure(size=self._ui_tokens.tiny)
            self._fonts["mono"].configure(size=self._ui_tokens.mono)
            self._fonts["mono_small"].configure(size=self._ui_tokens.mono_small)

    def refresh_ui_preferences(self) -> None:
        self._apply_ui_preferences()
        if "_dashboard_tab" in self.__dict__:
            self._dashboard_tab.apply_ui_preferences()
        if "_mods_tab" in self.__dict__:
            self._mods_tab.apply_ui_preferences()
        if "_server_tab" in self.__dict__:
            self._server_tab.apply_ui_preferences()
        if "_settings_tab" in self.__dict__:
            self._settings_tab.apply_ui_preferences()
        if "_about_tab" in self.__dict__:
            self._about_tab.apply_ui_preferences()
        if "_status" in self.__dict__:
            self._status.apply_ui_preferences(self)
        if "_recovery_tab" in self.__dict__ and self._recovery_tab is not None:
            self._recovery_tab.apply_ui_preferences()
        self.update_idletasks()

    @property
    def ui_tokens(self) -> UiTokens:
        return self._ui_tokens

    def ui_font(self, role: str):
        return self._fonts[role]

    def should_confirm(self, category: str) -> bool:
        mode = self.preferences.confirmation_mode
        if mode == "none":
            return False
        if category in {"destructive", "hosted", "conflict", "variant"}:
            return True
        if mode == "always":
            return True
        if mode == "destructive_only":
            return category == "bulk"
        return False

    def confirm_action(self, category: str, title: str, message: str) -> bool:
        if not self.should_confirm(category):
            return True
        return messagebox.askyesno(title, message)

    def center_dialog(self, window, width: int, height: int) -> None:
        try:
            self.update_idletasks()
            window.update_idletasks()
            x = self.winfo_rootx() + max(0, (self.winfo_width() - width) // 2)
            y = self.winfo_rooty() + max(0, (self.winfo_height() - height) // 2)
            window.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            window.geometry(f"{width}x{height}")

    def _record_action(self, action: str, *, target: str = "", display_name: str = "", notes: str = "") -> None:
        try:
            self.manifest.add_record(
                DeploymentRecord(
                    mod_id=f"app:{action}",
                    action=action,
                    target=target,
                    display_name=display_name,
                    notes=notes,
                )
            )
        except Exception as exc:
            log.warning("Could not record app action %s: %s", action, exc)

    def _running_process_names(self) -> set[str]:
        now = time.monotonic()
        if now - self._process_names_cache_at < 2.0 and self._process_names_cache:
            return set(self._process_names_cache)
        try:
            startupinfo = None
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
                startupinfo.wShowWindow = 0
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
                creationflags=creationflags,
                startupinfo=startupinfo,
            )
            names: set[str] = set()
            for raw_line in result.stdout.splitlines():
                line = raw_line.strip().strip('"')
                if not line:
                    continue
                first = line.split('","', 1)[0].strip('"')
                if first:
                    names.add(first.lower())
            self._process_names_cache = names
            self._process_names_cache_at = now
            return names
        except Exception as exc:
            log.warning("Could not query running processes: %s", exc)
            return set()

    def is_game_running(self) -> bool:
        names = self._running_process_names()
        return any(name in names for name in {"windrose.exe", "eosauthlauncher.exe"})

    def is_server_process_running(self) -> bool:
        names = self._running_process_names()
        return any(name in names for name in {"windroseserver.exe", "windroseserver-win64-shipping.exe"})

    # ---------------------------------------------------------- UI

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._recovery_window = None
        self._recovery_tab = None
        self._loaded_tabs: set[str] = set()

        self._build_update_banner()

        self._main_host = ctk.CTkFrame(self, fg_color="transparent")
        self._main_host.grid(row=1, column=0, sticky="nsew", padx=8, pady=(8, 8))
        self._main_host.grid_columnconfigure(0, weight=1)
        self._main_host.grid_rowconfigure(0, weight=1)

        self._tabview = ctk.CTkTabview(self._main_host, command=self._on_tab_changed)
        self._tabview.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        tab_dashboard = self._tabview.add("Dashboard")
        tab_mods = self._tabview.add("Mods")
        tab_server = self._tabview.add("Server")
        tab_activity = self._tabview.add("Activity")
        tab_settings = self._tabview.add("Settings")
        tab_help = self._tabview.add("Help")

        for tab in (tab_dashboard, tab_mods, tab_server, tab_activity, tab_settings, tab_help):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        from .tabs.backups_tab import BackupsTab
        from .tabs.dashboard_tab import DashboardTab
        from .tabs.mods_tab import ModsTab
        from .tabs.server_tab import ServerTab
        from .tabs.settings_tab import SettingsTab
        from .tabs.about_tab import AboutTab

        self._mods_tab = ModsTab(tab_mods, app=self)
        self._mods_tab.grid(row=0, column=0, sticky="nsew")

        self._server_tab = ServerTab(tab_server, app=self, defer_initial_refresh=True)
        self._server_tab.grid(row=0, column=0, sticky="nsew")

        self._dashboard_tab = DashboardTab(tab_dashboard, app=self)
        self._dashboard_tab.grid(row=0, column=0, sticky="nsew")

        tab_activity.grid_rowconfigure(0, weight=1)
        tab_activity.grid_rowconfigure(1, weight=0)
        activity_host = ctk.CTkFrame(tab_activity, fg_color="transparent")
        activity_host.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        activity_host.grid_columnconfigure(0, weight=1)
        activity_host.grid_rowconfigure(0, weight=1)
        self._recovery_tab = BackupsTab(activity_host, app=self, auto_refresh=False)
        self._recovery_tab.grid(row=0, column=0, sticky="nsew")

        status_host = ctk.CTkFrame(tab_activity, fg_color="transparent")
        status_host.grid(row=1, column=0, sticky="ew")
        status_host.grid_columnconfigure(0, weight=1)
        status_host.grid_rowconfigure(0, weight=1)

        self._settings_tab = SettingsTab(tab_settings, app=self)
        self._settings_tab.grid(row=0, column=0, sticky="nsew")

        self._about_tab = AboutTab(tab_help, app=self)
        self._about_tab.grid(row=0, column=0, sticky="nsew")

        self._build_launch_bar(self._main_host)

        self._status = StatusPanel(
            status_host,
            height=180,
            collapsed=True,
        )
        self._status.grid(row=0, column=0, sticky="nsew")
        self._pump_ui_queue()
        self._tabview.set("Dashboard")
        self._bind_shortcuts()
        self.refresh_ui_preferences()

    def _on_tab_changed(self, tab_name: str) -> None:
        if tab_name not in self._loaded_tabs:
            self._refresh_tab(tab_name)
            self._loaded_tabs.add(tab_name)

    def _refresh_tab(self, tab_name: str) -> None:
        if tab_name == "Dashboard":
            self._dashboard_tab.refresh_view()
        elif tab_name == "Mods":
            self._mods_tab.refresh_view()
        elif tab_name == "Server":
            self._server_tab.refresh_view()
        elif tab_name == "Activity":
            if self._recovery_tab is not None:
                self._recovery_tab.refresh()
        elif tab_name == "Settings":
            self._settings_tab.refresh_view()
        elif tab_name == "Help":
            self._about_tab.refresh_view()

    def dispatch_to_ui(self, callback) -> None:
        self._ui_call_queue.put(callback)

    def _pump_ui_queue(self) -> None:
        try:
            while True:
                callback = self._ui_call_queue.get_nowait()
                try:
                    callback()
                except Exception as exc:
                    log.warning("UI callback failed: %s", exc)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(50, self._pump_ui_queue)

    # ---------------------------------------------------------- update banner

    def _build_update_banner(self) -> None:
        """Hidden banner shown when a newer release exists on GitHub."""
        self._update_frame = ctk.CTkFrame(self, fg_color="#1a5276", height=36,
                                          corner_radius=0)
        self._update_frame.grid_columnconfigure(0, weight=1)
        self._update_label = ctk.CTkLabel(
            self._update_frame, text="", font=self.ui_font("body"),
            text_color="#d4efff",
        )
        self._update_label.pack(side="left", padx=12, pady=6)
        self._update_btn = ctk.CTkButton(
            self._update_frame, text="Download", width=90,
            height=self.ui_tokens.compact_button_height,
            font=self.ui_font("body"),
            fg_color="#2980b9", hover_color="#2471a3",
            command=self._on_update_primary_action,
        )
        self._update_btn.pack(side="right", padx=12, pady=6)
        self._update_later_btn = ctk.CTkButton(
            self._update_frame, text="Later", width=90,
            height=self.ui_tokens.compact_button_height,
            font=self.ui_font("body"),
            fg_color="#34495e", hover_color="#2c3e50",
            command=self._dismiss_update_banner,
        )
        self._update_later_btn.pack(side="right", padx=(0, 8), pady=6)
        self._update_release: ReleaseInfo | None = None
        self._downloaded_update_path: Path | None = None

    def _dismiss_update_banner(self) -> None:
        self._update_frame.grid_remove()

    def _on_update_primary_action(self) -> None:
        if self._downloaded_update_path:
            self._open_download_folder(self._downloaded_update_path)
            return

        if not self._update_release:
            return

        asset = self._update_release.preferred_asset
        if asset is None:
            if self._update_release.html_url:
                webbrowser.open(self._update_release.html_url)
            return

        self._update_btn.configure(state="disabled", text="Downloading...")
        self._update_later_btn.configure(state="disabled")
        self._update_label.configure(
            text=f"Downloading {asset.name} to your Downloads folder...",
        )
        download_release_asset(
            self._update_release,
            progress_callback=self._on_update_download_progress,
            complete_callback=self._on_update_download_complete,
        )

    def _show_update_banner(self, release: ReleaseInfo) -> None:
        """Called from the background update-check thread."""
        def _show():
            self._update_release = release
            self._downloaded_update_path = None
            button_text = "Download" if release.preferred_asset else "Open Release"
            self._update_btn.configure(state="normal", text=button_text)
            self._update_later_btn.configure(state="normal", text="Later")
            self._update_label.configure(
                text=f"A new version is available: v{release.version}  (you have v{__version__})"
            )
            self._update_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.dispatch_to_ui(_show)

    def _on_update_download_progress(self, downloaded: int, total: int, asset_name: str) -> None:
        def _show() -> None:
            if total > 0:
                percent = min(100, int(downloaded * 100 / total))
                self._update_label.configure(
                    text=f"Downloading {asset_name}... {percent}%"
                )
            else:
                mb = downloaded / (1024 * 1024)
                self._update_label.configure(
                    text=f"Downloading {asset_name}... {mb:.1f} MB"
                )

        self.dispatch_to_ui(_show)

    def _on_update_download_complete(self, path: Path | None, error: str | None) -> None:
        def _show() -> None:
            if error:
                self._update_btn.configure(state="normal", text="Retry")
                self._update_later_btn.configure(state="normal", text="Close")
                self._update_label.configure(
                    text=f"Update download failed: {error}",
                    text_color="#f5c6cb",
                )
                return

            self._downloaded_update_path = path
            self._update_btn.configure(state="normal", text="Open Folder")
            self._update_later_btn.configure(state="normal", text="Close")
            self._update_label.configure(
                text=f"Downloaded v{self._update_release.version} to {path.parent}",
                text_color="#d4efff",
            )

        self.dispatch_to_ui(_show)

    def _open_download_folder(self, path: Path) -> None:
        if path.exists():
            subprocess.Popen(["explorer", f"/select,{path}"])
        elif path.parent.exists():
            subprocess.Popen(["explorer", str(path.parent)])

    # ---------------------------------------------------------- launch bar

    def _build_launch_bar(self, parent) -> None:
        bar = ctk.CTkFrame(parent, fg_color="transparent", height=40)
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 0))
        bar.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        self._launch_game_btn = ctk.CTkButton(
            inner, text="Launch Windrose", width=136,
            height=self.ui_tokens.button_height,
            font=self.ui_font("body"),
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_start_game,
        )
        self._launch_game_btn.pack(side="left", padx=4)

        self._launch_server_btn = ctk.CTkButton(
            inner, text="Launch Dedicated Server", width=172,
            height=self.ui_tokens.button_height,
            font=self.ui_font("body"),
            fg_color="#555555", hover_color="#666666",
            command=self._on_start_server,
        )
        self._launch_server_btn.pack(side="left", padx=4)

        badge_frame = ctk.CTkFrame(bar, fg_color="transparent")
        badge_frame.place(relx=1.0, rely=0.5, anchor="e")
        self._mod_count_label = ctk.CTkLabel(
            badge_frame, text="",
            font=self.ui_font("small"), text_color="#95a5a6",
        )
        self._mod_count_label.pack(padx=8)

    def _on_start_game(self) -> None:
        exe = self.paths.client_root / "Windrose.exe" if self.paths.client_root else None
        if exe and exe.is_file():
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
            log.info("Launched game: %s", exe)
            self._record_action("launch_game", target="client", display_name="Windrose", notes=f"Launched {exe}")
        else:
            messagebox.showerror("Not Found",
                                 "Windrose.exe not found. Check client path in Settings.")

    def _launch_server_root(self, root: Path | None, *, label: str) -> bool:
        if root:
            bat = root / "StartServerForeground.bat"
            exe = root / "WindroseServer.exe"
            target = bat if bat.is_file() else exe
        else:
            target = None

        if not target or not target.is_file():
            messagebox.showerror(
                "Not Found",
                f"{label} executable not found. Check the corresponding server path in Settings.",
            )
            return False

        try:
            creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            if target.suffix.lower() in {".bat", ".cmd"}:
                subprocess.Popen(
                    ["cmd.exe", "/c", str(target)],
                    cwd=str(target.parent),
                    creationflags=creation_flags,
                )
            else:
                subprocess.Popen(
                    [str(target)],
                    cwd=str(target.parent),
                    creationflags=creation_flags,
                )
            log.info("Launched %s: %s", label.lower(), target)
            record_action = getattr(self, "_record_action", None)
            if callable(record_action):
                record_action(
                    "launch_server",
                    target="server" if "local" in label.lower() else "dedicated_server",
                    display_name=label,
                    notes=f"Launched {target}",
                )
            return True
        except Exception as exc:
            log.error("Failed to launch %s %s: %s", label.lower(), target, exc)
            messagebox.showerror(
                "Launch Failed",
                f"Could not launch the {label.lower()}.\n"
                f"{exc}",
            )
            return False

    def _on_start_server(self) -> bool:
        return self._launch_server_root(self.paths.dedicated_server_root, label="Dedicated Server")

    def _on_start_windrose_plus_server(self) -> bool:
        root = self.paths.dedicated_server_root
        target = root / "StartWindrosePlusServer.bat" if root else None
        if not target or not target.is_file():
            messagebox.showerror("Not Found", "StartWindrosePlusServer.bat was not found in the dedicated server root.")
            return False
        return self._launch_specific_server_file(target, label="WindrosePlus Server")

    def _launch_specific_server_file(self, target: Path, *, label: str) -> bool:
        try:
            creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(
                ["cmd.exe", "/k", "call", str(target)] if target.suffix.lower() in {".bat", ".cmd"} else [str(target)],
                cwd=str(target.parent),
                creationflags=creation_flags,
            )
            self._record_action(
                "launch_server",
                target="dedicated_server",
                display_name=label,
                notes=f"Launched {target}",
            )
            return True
        except Exception as exc:
            log.error("Failed to launch %s %s: %s", label.lower(), target, exc)
            messagebox.showerror("Launch Failed", f"Could not launch {label}.\n{exc}")
            return False

    # ---------------------------------------------------------- lifecycle

    def _initial_load(self) -> None:
        """Run first-time discovery if no game or server path is configured."""
        if not self.paths.client_root and not self.paths.server_root and not self.paths.dedicated_server_root:
            log.info("No client or server roots configured — running auto-detection...")
            stage_started = time.perf_counter()
            detected = discover_all()
            self._log_startup_timing("_initial_load.discover_all", stage_started)
            if detected.client_root:
                self.paths.client_root = detected.client_root
                log.info("Auto-detected client: %s", detected.client_root)
            if detected.server_root:
                self.paths.server_root = detected.server_root
                log.info("Auto-detected local server: %s", detected.server_root)
            if detected.dedicated_server_root:
                self.paths.dedicated_server_root = detected.dedicated_server_root
                log.info("Auto-detected dedicated server: %s", detected.dedicated_server_root)
            if detected.local_config:
                self.paths.local_config = detected.local_config
            if detected.local_save_root:
                self.paths.local_save_root = detected.local_save_root
            self.save_settings()

        stage_started = time.perf_counter()
        self._update_mod_badge()
        if "_dashboard_tab" in self.__dict__:
            self._dashboard_tab.refresh_view()
            self._loaded_tabs.add("Dashboard")
        self._log_startup_timing("_initial_load.refresh_initial_tab", stage_started)
        stage_started = time.perf_counter()
        self.after(400, self._warn_on_manifest_drift)
        self._log_startup_timing("_initial_load.defer_manifest_drift_scan", stage_started)

        stage_started = time.perf_counter()
        check_for_update(__version__, self._show_update_banner)
        self._log_startup_timing("_initial_load.schedule_update_check", stage_started)
        self.after(300, self._maybe_show_welcome)

    # ---------------------------------------------------------- cross-tab helpers

    def refresh_installed_tab(self) -> None:
        if "_dashboard_tab" in self.__dict__:
            self._dashboard_tab.refresh_view()
        self._mods_tab.refresh_view()
        if self._tabview.get() == "Server":
            self._server_tab.refresh_view()
        else:
            self._server_tab.refresh_remote_profiles()
        if self._recovery_tab is not None and ("Activity" in self._loaded_tabs or self._tabview.get() == "Activity"):
            self._recovery_tab.refresh()
        self._update_mod_badge()

    def refresh_backups_tab(self) -> None:
        if self._recovery_tab is not None and ("Activity" in self._loaded_tabs or self._tabview.get() == "Activity"):
            self._recovery_tab.refresh()
        if "_dashboard_tab" in self.__dict__:
            self._dashboard_tab.refresh_view()

    def refresh_mods_tab(self) -> None:
        if "_dashboard_tab" in self.__dict__:
            self._dashboard_tab.refresh_view()
        self._mods_tab.refresh_view()
        if self._tabview.get() == "Server":
            self._server_tab.refresh_view()
        else:
            self._server_tab.refresh_remote_profiles()
        self._update_mod_badge()

    def open_recovery_center(self) -> None:
        self._tabview.set("Activity")
        self._on_tab_changed("Activity")

    def open_restore_vanilla_dialog(self, target: str | None = None) -> None:
        target_values = ["Client", "Local Server", "Dedicated Server"]
        target_keys = {
            "Client": "client",
            "Local Server": "server",
            "Dedicated Server": "dedicated_server",
        }
        reverse_labels = {value: label for label, value in target_keys.items()}
        initial_label = reverse_labels.get(target or "", None)
        if initial_label is None:
            if self.paths.dedicated_server_root:
                initial_label = "Dedicated Server"
            elif self.paths.server_root:
                initial_label = "Local Server"
            else:
                initial_label = "Client"

        dialog = ctk.CTkToplevel(self)
        dialog.title("Restore Vanilla")
        self.center_dialog(dialog, 880, 700)
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(5, weight=1)

        title_label = ctk.CTkLabel(dialog, text=f"Restore Vanilla: {initial_label}", font=self.ui_font("title"))
        title_label.grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 4)
        )
        ctk.CTkLabel(
            dialog,
            text="This removes selected mod files from this target only. Saves and server settings are not changed.",
            text_color="#95a5a6",
            font=self.ui_font("body"),
            justify="left",
            wraplength=820,
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        control_row = ctk.CTkFrame(dialog, fg_color="transparent")
        control_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        ctk.CTkLabel(control_row, text="Target:", font=self.ui_font("body")).pack(side="left")
        target_var = ctk.StringVar(value=initial_label)
        ctk.CTkOptionMenu(
            control_row,
            values=target_values,
            variable=target_var,
            width=220,
            font=self.ui_font("body"),
            command=lambda _choice: refresh_plan(reset_defaults=True),
        ).pack(side="left", padx=(8, 0))

        check_row = ctk.CTkFrame(dialog, fg_color="transparent")
        check_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 8))
        managed_var = tk.BooleanVar(value=False)
        unmanaged_var = tk.BooleanVar(value=False)
        frameworks_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(check_row, text="Managed mods", variable=managed_var, font=self.ui_font("body")).pack(side="left", padx=(0, 14))
        ctk.CTkCheckBox(check_row, text="Unmanaged ~mods files", variable=unmanaged_var, font=self.ui_font("body")).pack(side="left", padx=(0, 14))
        ctk.CTkCheckBox(check_row, text="Framework files", variable=frameworks_var, font=self.ui_font("body")).pack(side="left", padx=(0, 14))

        status_label = ctk.CTkLabel(dialog, text="", text_color="#95a5a6", font=self.ui_font("small"), justify="left")
        status_label.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 6))

        preview = ctk.CTkTextbox(dialog, font=self.ui_font("mono_small"), wrap="word")
        preview.grid(row=5, column=0, sticky="nsew", padx=16, pady=(0, 10))

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 16))

        current_plan: dict[str, RestoreVanillaPlan | None] = {"value": None}

        def write_preview(plan: RestoreVanillaPlan) -> None:
            preview.configure(state="normal")
            preview.delete("1.0", "end")
            preview.insert("1.0", self._restore_vanilla_preview_text(plan))
            preview.configure(state="disabled")

        def refresh_plan(*, reset_defaults: bool = False) -> None:
            try:
                plan = self.restore_vanilla.build_plan(target_keys[target_var.get()])
            except Exception as exc:
                current_plan["value"] = None
                preview.configure(state="normal")
                preview.delete("1.0", "end")
                preview.insert("1.0", str(exc))
                preview.configure(state="disabled")
                status_label.configure(text="Could not build restore plan.", text_color="#c0392b")
                execute_btn.configure(state="disabled")
                return

            current_plan["value"] = plan
            dialog.title(f"Restore Vanilla: {plan.target_label}")
            title_label.configure(text=f"Restore Vanilla: {plan.target_label}")
            if reset_defaults:
                managed_var.set(bool(plan.managed_mods))
                unmanaged_var.set(bool(plan.unmanaged_files))
                frameworks_var.set(False)
            write_preview(plan)
            if plan.root is None:
                status_label.configure(text="Target path is not configured.", text_color="#e67e22")
                execute_btn.configure(state="disabled")
            elif not plan.has_actions:
                status_label.configure(text="No mod or framework files were found for this target.", text_color="#95a5a6")
                execute_btn.configure(state="disabled")
            else:
                status_label.configure(text="Review the preview and choose what to remove.", text_color="#95a5a6")
                execute_btn.configure(state="normal")

        def execute() -> None:
            plan = current_plan["value"]
            if plan is None:
                return
            selected_count = sum(
                [
                    bool(managed_var.get() and plan.managed_mods),
                    bool(unmanaged_var.get() and plan.unmanaged_files),
                    bool(frameworks_var.get() and plan.framework_files),
                ]
            )
            if selected_count == 0:
                status_label.configure(text="Choose at least one cleanup section first.", text_color="#e67e22")
                return
            if not self.confirm_action(
                "destructive",
                "Restore Vanilla",
                (
                    f"Remove the selected mod files from {plan.target_label}?\n\n"
                    "Backups are created first. Saves, server settings, hosted files, and the inactive archive library are not touched."
                ),
            ):
                return
            execute_btn.configure(state="disabled", text="Cleaning...")
            self.update_idletasks()
            result = self.restore_vanilla.execute_plan(
                plan,
                include_managed=managed_var.get(),
                include_unmanaged=unmanaged_var.get(),
                include_frameworks=frameworks_var.get(),
            )
            self.refresh_installed_tab()
            self.refresh_backups_tab()
            refresh_plan(reset_defaults=True)
            execute_btn.configure(text="Restore Vanilla")
            if result.errors:
                status_label.configure(text="Restore completed with errors: " + "; ".join(result.errors[:3]), text_color="#e67e22")
            else:
                message = (
                    f"Removed {result.removed_managed} managed, {result.removed_unmanaged} unmanaged, "
                    f"{result.removed_frameworks} framework item(s). Backups: {result.backups_created}."
                )
                if result.warnings:
                    message += " " + " ".join(result.warnings)
                status_label.configure(text=message, text_color="#2d8a4e")

        execute_btn = ctk.CTkButton(
            buttons,
            text="Restore Vanilla",
            width=140,
            fg_color="#c0392b",
            hover_color="#a93226",
            command=execute,
        )
        execute_btn.pack(side="left")
        ctk.CTkButton(
            buttons,
            text="Refresh Preview",
            width=130,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: refresh_plan(reset_defaults=True),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            buttons,
            text="Cancel",
            width=100,
            fg_color="#444444",
            hover_color="#555555",
            command=dialog.destroy,
        ).pack(side="right")

        refresh_plan(reset_defaults=True)

    @staticmethod
    def _restore_vanilla_preview_text(plan: RestoreVanillaPlan) -> str:
        lines = [
            f"Target: {plan.target_label}",
            f"Root: {plan.root or 'Not configured'}",
            "",
        ]
        if plan.warnings:
            lines.append("Warnings")
            lines.extend(f"- {warning}" for warning in plan.warnings)
            lines.append("")

        def add_section(title: str, items) -> None:
            lines.append(title)
            if not items:
                lines.append("- None")
            else:
                for item in items:
                    detail = f" | {item.detail}" if item.detail else ""
                    lines.append(f"- {item.label}{detail}")
            lines.append("")

        add_section("Managed mods", plan.managed_mods)
        add_section("Unmanaged ~mods files", plan.unmanaged_files)
        add_section("Framework files", plan.framework_files)
        add_section("Needs manual review", plan.managed_review)
        lines.append("Not touched")
        lines.append("- Saves / worlds")
        lines.append("- ServerDescription.json and WorldDescription.json")
        lines.append("- Hosted / remote server files")
        lines.append("- Inactive archive library")
        lines.append("- Backup history")
        return "\n".join(lines)

    def manifest_drift_warnings(self) -> list[str]:
        return list(self._manifest_drift_warnings)

    def set_last_hosted_diagnostics(self, text: str) -> None:
        self._last_hosted_diagnostics = text or ""

    def build_support_report(self) -> str:
        return self.support_diagnostics.build_report(
            paths=self.paths,
            manifest=self.manifest,
            remote_profiles=self.remote_profiles,
            framework_state=self.framework_state,
            data_dir=self.paths.data_dir or DEFAULT_DATA_DIR,
            backup_root=self.backup.backup_root,
            last_hosted_diagnostics=self._last_hosted_diagnostics,
        )

    def open_remote_deploy(self, archive_path: str | Path | None = None) -> None:
        self._server_tab.open_hosted_install_dialog(archive_path)

    def refresh_remote_profile_views(self) -> None:
        self._server_tab.refresh_remote_profiles()

    def _update_mod_badge(self) -> None:
        count = len(self.manifest.list_mods())
        if count:
            self._mod_count_label.configure(text=f"{count} mod{'s' if count != 1 else ''} installed")
        else:
            self._mod_count_label.configure(text="")

    def _warn_on_manifest_drift(self) -> None:
        def _work() -> None:
            drift_warnings = self.integrity.scan_manifest_drift(self.manifest.list_mods())
            for warning in drift_warnings:
                log.warning("Managed mod drift detected: %s", warning)
            def _show() -> None:
                self._manifest_drift_warnings = list(drift_warnings)
                if "_dashboard_tab" in self.__dict__:
                    self._dashboard_tab.refresh_view()
            self.dispatch_to_ui(_show)

        threading.Thread(target=_work, daemon=True).start()

    def _bind_shortcuts(self) -> None:
        self.bind("<F5>", lambda _event: self._refresh_active_view())
        self.bind("<Control-o>", lambda _event: self._mods_tab.import_archives())
        self.bind("<Control-r>", lambda _event: self._refresh_active_view())
        self.bind("<Control-Shift-R>", lambda _event: self.open_recovery_center())

    def _refresh_active_view(self) -> None:
        current = self._tabview.get()
        self._refresh_tab(current)
        self._loaded_tabs.add(current)

    def _maybe_show_welcome(self) -> None:
        should_show = self._first_run and self.preferences.show_welcome
        if should_show:
            self._show_welcome_dialog()

    def _show_welcome_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Welcome to Windrose Mod Manager")
        self.center_dialog(dialog, 540, 370)
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        body = ctk.CTkFrame(dialog)
        body.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            body,
            text="Windrose Client + Server Cockpit",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 6))

        ctk.CTkLabel(
            body,
            text=(
                "Use Mods for archives and applied installs, Server for local, dedicated, or hosted settings, "
                "and Activity & Backups when you need to undo or restore changes."
            ),
            justify="left",
            wraplength=460,
            text_color="#b7c0c7",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        status_lines = [
            f"Client path: {self.paths.client_root or 'Not set'}",
            f"Local server path: {self.paths.server_root or 'Not set'}",
            f"Dedicated server path: {self.paths.dedicated_server_root or 'Not set'}",
            f"Hosted profiles: {len(self.remote_profiles.list_profiles())}",
        ]
        ctk.CTkLabel(
            body,
            text="\n".join(status_lines),
            justify="left",
            wraplength=460,
            text_color="#95a5a6",
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))

        action_frame = ctk.CTkFrame(body, fg_color="transparent")
        action_frame.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 10))

        dont_show_var = tk.BooleanVar(value=not self.preferences.show_welcome)

        def _close_dialog() -> None:
            self.preferences.show_welcome = not bool(dont_show_var.get())
            self.save_settings()
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", _close_dialog)

        def _go_library() -> None:
            self._tabview.set("Mods")
            _close_dialog()
            self._mods_tab.import_archives()

        def _go_server() -> None:
            self._tabview.set("Server")
            _close_dialog()
            self._server_tab.open_hosted_setup()

        def _go_settings() -> None:
            self._tabview.set("Settings")
            _close_dialog()

        ctk.CTkButton(
            action_frame,
            text="Import First Archive",
            width=150,
            fg_color="#2d8a4e",
            hover_color="#236b3d",
            command=_go_library,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            action_frame,
            text="Set Up Hosted Server",
            width=150,
            fg_color="#2980b9",
            hover_color="#2471a3",
            command=_go_server,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            action_frame,
            text="Review Paths",
            width=120,
            fg_color="#555555",
            hover_color="#666666",
            command=_go_settings,
        ).pack(side="left", padx=8)

        ctk.CTkCheckBox(
            body,
            text="Don't show this again",
            variable=dont_show_var,
            onvalue=True,
            offvalue=False,
            font=self.ui_font("body"),
        ).grid(row=4, column=0, sticky="w", padx=14, pady=(0, 4))

        ctk.CTkButton(
            body,
            text="Close",
            width=120,
            fg_color="#444444",
            hover_color="#555555",
            command=_close_dialog,
        ).grid(row=5, column=0, sticky="e", padx=14, pady=(6, 14))
