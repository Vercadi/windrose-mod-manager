"""Main application window — assembles all tabs and services."""
from __future__ import annotations

import logging
import subprocess
import threading
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
from ..core.installer import Installer
from ..core.logging_service import setup_logging
from ..core.manifest_store import ManifestStore
from ..core.recovery_service import RecoveryService
from ..core.remote_deployer import RemoteDeploymentService
from ..core.remote_config_service import RemoteConfigService
from ..core.remote_profile_store import RemoteProfileStore
from ..core.server_config_service import ServerConfigService
from ..core.server_sync_service import ServerSyncService
from ..core.update_checker import ReleaseInfo, check_for_update, download_release_asset
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
        self._first_run = not SETTINGS_FILE.is_file()
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
        reconciled_paths, changed = reconcile_paths(self.paths)
        if changed:
            old_server_root = self.paths.server_root
            old_save_root = self.paths.local_save_root
            self.paths = reconciled_paths
            self.save_settings()
            log.info(
                "Reconciled saved paths. Server root: %s -> %s | Save root: %s -> %s",
                old_server_root,
                self.paths.server_root,
                old_save_root,
                self.paths.local_save_root,
            )
        else:
            self.paths = reconciled_paths

        self._rebind_backup_services()
        self.manifest = ManifestStore(self.paths.data_dir)
        self.remote_profiles = RemoteProfileStore(self.paths.data_dir)
        self.remote_deployer = RemoteDeploymentService()
        self.remote_config_svc = RemoteConfigService(self.backup, self.remote_profiles)
        self.recovery = RecoveryService(self.manifest, self.backup)
        self.server_sync = ServerSyncService()

        log.info("Services initialized")

    def _rebind_backup_services(self) -> None:
        """Recreate services that are bound to the current backup root."""
        backup_dir = self.paths.backup_dir or DEFAULT_BACKUP_DIR
        ensure_dir(backup_dir)
        self.backup = BackupManager(backup_dir)
        self.installer = Installer(self.backup)
        self.server_config_svc = ServerConfigService(self.backup)
        self.world_config_svc = WorldConfigService(self.backup)
        self.integrity = IntegrityService(self.paths, self.backup)
        if "remote_profiles" in self.__dict__:
            self.remote_config_svc = RemoteConfigService(self.backup, self.remote_profiles)
        if "manifest" in self.__dict__:
            self.recovery = RecoveryService(self.manifest, self.backup)
        log.info("Rebound backup-backed services to %s", backup_dir)

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
        self.grid_rowconfigure(1, weight=1)
        self._status_collapsed_height = 38
        self._status_expanded_height = 180
        self._recovery_window = None
        self._recovery_tab = None

        self._build_update_banner()

        self._main_panes = tk.PanedWindow(
            self,
            orient=tk.VERTICAL,
            sashwidth=8,
            showhandle=True,
            handlesize=8,
            bd=0,
            relief=tk.FLAT,
            bg="#2b2b2b",
            sashrelief=tk.RAISED,
        )
        self._main_panes.grid(row=1, column=0, sticky="nsew", padx=8, pady=(8, 8))

        self._main_host = ctk.CTkFrame(self._main_panes, fg_color="transparent")
        self._main_host.grid_columnconfigure(0, weight=1)
        self._main_host.grid_rowconfigure(0, weight=1)

        self._status_host = ctk.CTkFrame(self._main_panes, fg_color="transparent")
        self._status_host.grid_columnconfigure(0, weight=1)
        self._status_host.grid_rowconfigure(0, weight=1)

        self._main_panes.add(self._main_host, minsize=380, height=560, stretch="always")
        self._main_panes.add(self._status_host, minsize=110, height=150, stretch="never")

        self._tabview = ctk.CTkTabview(self._main_host)
        self._tabview.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        tab_mods = self._tabview.add("Mods")
        tab_server = self._tabview.add("Server")
        tab_settings = self._tabview.add("Settings")
        tab_help = self._tabview.add("Help")

        for tab in (tab_mods, tab_server, tab_settings, tab_help):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        from .tabs.mods_tab import ModsTab
        from .tabs.server_tab import ServerTab
        from .tabs.settings_tab import SettingsTab
        from .tabs.about_tab import AboutTab

        self._mods_tab = ModsTab(tab_mods, app=self)
        self._mods_tab.grid(row=0, column=0, sticky="nsew")

        self._server_tab = ServerTab(tab_server, app=self)
        self._server_tab.grid(row=0, column=0, sticky="nsew")

        self._settings_tab = SettingsTab(tab_settings, app=self)
        self._settings_tab.grid(row=0, column=0, sticky="nsew")

        self._about_tab = AboutTab(tab_help, app=self)
        self._about_tab.grid(row=0, column=0, sticky="nsew")

        self._build_launch_bar(self._main_host)

        self._status = StatusPanel(
            self._status_host,
            height=140,
            toggle_callback=self._toggle_technical_log,
            collapsed=True,
        )
        self._status.grid(row=0, column=0, sticky="nsew")
        self.after(150, self._set_initial_split_positions)
        self._tabview.set("Mods")
        self._bind_shortcuts()

    def _set_initial_split_positions(self) -> None:
        """Default to a compact status log while keeping it user-resizable."""
        try:
            total_height = max(self.winfo_height(), 700)
            status_height = (
                self._status_collapsed_height
                if self._status.is_collapsed
                else self._status_expanded_height
            )
            self._main_panes.sash_place(0, 0, total_height - status_height)
        except tk.TclError:
            pass

    def _toggle_technical_log(self, collapsed: bool) -> None:
        def _apply() -> None:
            try:
                total_height = max(self.winfo_height(), 700)
                status_height = (
                    self._status_collapsed_height
                    if collapsed
                    else self._status_expanded_height
                )
                self._main_panes.sash_place(0, 0, total_height - status_height)
            except tk.TclError:
                pass

        self.after(0, _apply)

    # ---------------------------------------------------------- update banner

    def _build_update_banner(self) -> None:
        """Hidden banner shown when a newer release exists on GitHub."""
        self._update_frame = ctk.CTkFrame(self, fg_color="#1a5276", height=36,
                                          corner_radius=0)
        self._update_frame.grid_columnconfigure(0, weight=1)
        self._update_label = ctk.CTkLabel(
            self._update_frame, text="", font=ctk.CTkFont(size=12),
            text_color="#d4efff",
        )
        self._update_label.pack(side="left", padx=12, pady=6)
        self._update_btn = ctk.CTkButton(
            self._update_frame, text="Download", width=90,
            fg_color="#2980b9", hover_color="#2471a3",
            command=self._on_update_primary_action,
        )
        self._update_btn.pack(side="right", padx=12, pady=6)
        self._update_later_btn = ctk.CTkButton(
            self._update_frame, text="Later", width=90,
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
        self.after(0, _show)

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

        self.after(0, _show)

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

        self.after(0, _show)

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
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_start_game,
        )
        self._launch_game_btn.pack(side="left", padx=4)

        self._launch_server_btn = ctk.CTkButton(
            inner, text="Launch Dedicated Server", width=172,
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
            log.info("Launched dedicated server: %s", target)
        else:
            messagebox.showerror("Not Found",
                                 "Dedicated server executable not found. Check server path in Settings.")

    # ---------------------------------------------------------- lifecycle

    def _initial_load(self) -> None:
        """Run first-time discovery if no game or server path is configured."""
        if not self.paths.client_root and not self.paths.server_root:
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

        self._mods_tab.refresh_view()
        self._server_tab.refresh_view()
        self._about_tab.refresh_view()
        if self._recovery_tab is not None:
            self._recovery_tab.refresh()
        self._warn_on_manifest_drift()

        check_for_update(__version__, self._show_update_banner)
        self.after(300, self._maybe_show_welcome)

    # ---------------------------------------------------------- cross-tab helpers

    def refresh_installed_tab(self) -> None:
        self._mods_tab.refresh_view()
        self._server_tab.refresh_view()
        if self._recovery_tab is not None:
            self._recovery_tab.refresh()
        self._update_mod_badge()

    def refresh_backups_tab(self) -> None:
        if self._recovery_tab is not None:
            self._recovery_tab.refresh()

    def refresh_mods_tab(self) -> None:
        self._mods_tab.refresh_view()
        self._server_tab.refresh_view()
        self._update_mod_badge()

    def open_recovery_center(self) -> None:
        if self._recovery_window is not None and self._recovery_window.winfo_exists():
            self._recovery_window.focus()
            self._recovery_window.lift()
            if self._recovery_tab is not None:
                self._recovery_tab.refresh()
            return

        window = ctk.CTkToplevel(self)
        window.title("Recovery")
        window.geometry("1120x720")
        window.minsize(900, 560)
        window.transient(self)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(0, weight=1)

        from .tabs.backups_tab import BackupsTab

        recovery_tab = BackupsTab(window, app=self)
        recovery_tab.grid(row=0, column=0, sticky="nsew")

        def _on_close() -> None:
            self._recovery_tab = None
            self._recovery_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", _on_close)
        self._recovery_window = window
        self._recovery_tab = recovery_tab

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

        threading.Thread(target=_work, daemon=True).start()

    def _bind_shortcuts(self) -> None:
        self.bind("<F5>", lambda _event: self._refresh_active_view())
        self.bind("<Control-o>", lambda _event: self._mods_tab.import_archives())
        self.bind("<Control-r>", lambda _event: self._refresh_active_view())
        self.bind("<Control-Shift-R>", lambda _event: self.open_recovery_center())

    def _refresh_active_view(self) -> None:
        current = self._tabview.get()
        if current == "Mods":
            self._mods_tab.refresh_view()
        elif current == "Server":
            self._server_tab.refresh_view()
        elif current == "Settings":
            self._settings_tab.refresh_view()
        elif current == "Help":
            self._about_tab.refresh_view()

    def _maybe_show_welcome(self) -> None:
        should_show = self._first_run or not self.manifest.list_mods()
        if should_show:
            self._show_welcome_dialog()

    def _show_welcome_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Welcome to Windrose Mod Manager")
        dialog.geometry("540x330")
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
                "Use Mods for archives and applied installs, Server for local or hosted settings, "
                "and Recovery when you need to undo or restore changes."
            ),
            justify="left",
            wraplength=460,
            text_color="#b7c0c7",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        status_lines = [
            f"Client path: {self.paths.client_root or 'Not set'}",
            f"Server path: {self.paths.server_root or 'Not set'}",
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

        def _go_library() -> None:
            self._tabview.set("Mods")
            dialog.destroy()
            self._mods_tab.import_archives()

        def _go_server() -> None:
            self._tabview.set("Server")
            dialog.destroy()
            self._server_tab.open_hosted_setup()

        def _go_settings() -> None:
            self._tabview.set("Settings")
            dialog.destroy()

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

        ctk.CTkButton(
            body,
            text="Close",
            width=120,
            fg_color="#444444",
            hover_color="#555555",
            command=dialog.destroy,
        ).grid(row=4, column=0, sticky="e", padx=14, pady=(6, 14))
