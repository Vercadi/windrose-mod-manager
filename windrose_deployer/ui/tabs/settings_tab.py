"""Settings screen for app-level configuration only."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk

from ...core.discovery import discover_all
from ...core.validators import (
    validate_client_root,
    validate_local_config,
    validate_server_root,
)

if TYPE_CHECKING:
    from ..app_window import AppWindow

log = logging.getLogger(__name__)


class SettingsTab(ctk.CTkFrame):
    def __init__(self, master, app: "AppWindow", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._path_vars: dict[str, ctk.StringVar] = {}
        self._status_labels: dict[str, ctk.CTkLabel] = {}
        self._hosted_profile_rows: list[ctk.CTkFrame] = []
        self._explicit_path_values: dict[str, str] = {}

        self._build_header()
        self._build_tabs()
        self._populate()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="Settings",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(14, 10), pady=(12, 4))

        ctk.CTkLabel(
            header,
            text=(
                "App-level setup only: client paths, bundled and dedicated server paths, hosted profiles, "
                "backup storage, and update behavior."
            ),
            justify="left",
            wraplength=640,
            text_color="#b7c0c7",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=2, sticky="e", padx=14, pady=10)

        ctk.CTkButton(actions, text="Auto-Detect", width=100, command=self._on_autodetect).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Validate",
            width=88,
            fg_color="#555555",
            hover_color="#666666",
            command=self._on_validate,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            actions,
            text="Save",
            width=88,
            fg_color="#2d8a4e",
            hover_color="#236b3d",
            command=self._on_save,
        ).pack(side="left", padx=(6, 0))

    def _build_tabs(self) -> None:
        self._tabs = ctk.CTkTabview(self)
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self._tab_client = self._tabs.add("Client")
        self._tab_server = self._tabs.add("Server")
        self._tab_hosted = self._tabs.add("Hosted")
        self._tab_backups = self._tabs.add("Backups")
        self._tab_updates = self._tabs.add("Updates")
        self._tab_advanced = self._tabs.add("Advanced")

        for tab in (
            self._tab_client,
            self._tab_server,
            self._tab_hosted,
            self._tab_backups,
            self._tab_updates,
            self._tab_advanced,
        ):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        self._build_client_tab()
        self._build_server_tab()
        self._build_hosted_tab()
        self._build_backups_tab()
        self._build_updates_tab()
        self._build_advanced_tab()

    def _build_client_tab(self) -> None:
        card = self._section_card(self._tab_client, 0, "Client")
        self._add_path_row(card, 1, "client_root", "Windrose Client Folder")
        self._add_path_row(card, 2, "local_config", "Local Config Folder")
        ctk.CTkLabel(
            card,
            text="Launch Windrose uses the client folder configured here.",
            justify="left",
            wraplength=760,
            text_color="#95a5a6",
        ).grid(row=3, column=0, columnspan=4, sticky="ew", padx=14, pady=(2, 14))

    def _build_server_tab(self) -> None:
        card = self._section_card(self._tab_server, 0, "Server Targets")
        self._add_path_row(card, 1, "server_root", "Bundled Server Folder")
        self._add_path_row(card, 2, "dedicated_server_root", "Dedicated Server Folder")
        self._add_path_row(card, 3, "local_save_root", "Dedicated Server World Saves Folder")
        ctk.CTkLabel(
            card,
            text=(
                "Bundled Server Folder should point at <Windrose>/R5/Builds/WindowsServer. "
                "Dedicated Server Folder should point at the standalone Windrose Dedicated Server install. "
                "Bundled server world files are derived from <bundled>/R5/Saved. Dedicated server launch and "
                "dedicated server/world settings use the dedicated server folder, and world saves default to "
                "<dedicated>/R5/Saved."
            ),
            justify="left",
            wraplength=760,
            text_color="#95a5a6",
        ).grid(row=4, column=0, columnspan=4, sticky="ew", padx=14, pady=(2, 14))

    def _build_hosted_tab(self) -> None:
        card = self._section_card(self._tab_hosted, 0, "Hosted Profiles")
        card.grid(sticky="nsew")
        card.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(
            card,
            text=(
                "Hosted profiles are app configuration. Use these profiles from the Server screen when you compare, "
                "apply settings, or install to a rented server."
            ),
            justify="left",
            wraplength=760,
            text_color="#95a5a6",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))
        ctk.CTkButton(
            actions,
            text="Manage Hosted Profiles",
            width=162,
            fg_color="#2980b9",
            hover_color="#2471a3",
            command=self._open_hosted_profile_manager,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Open Server Screen",
            width=138,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: self.app._tabview.set("Server"),
        ).pack(side="left", padx=6)

        self._hosted_summary = ctk.CTkLabel(card, text="", justify="left", text_color="#c1c7cd")
        self._hosted_summary.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 8))

        self._hosted_list = ctk.CTkScrollableFrame(card)
        self._hosted_list.grid(row=4, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self._hosted_list.grid_columnconfigure(0, weight=1)

    def _build_backups_tab(self) -> None:
        card = self._section_card(self._tab_backups, 0, "Backups and Recovery")
        self._add_path_row(card, 1, "backup_dir", "Backup Storage Folder")
        ctk.CTkLabel(
            card,
            text=(
                "Backup copies are created before managed installs and before config writes. "
                "Use Recovery to restore previous versions or clean up old backups."
            ),
            justify="left",
            wraplength=760,
            text_color="#95a5a6",
        ).grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=(2, 10))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=3, column=0, columnspan=4, sticky="w", padx=14, pady=(0, 14))
        ctk.CTkButton(actions, text="Open Backup Storage", width=150, command=lambda: self._open_path("backup_dir")).pack(
            side="left", padx=(0, 6)
        )
        ctk.CTkButton(
            actions,
            text="Open Recovery",
            width=118,
            fg_color="#555555",
            hover_color="#666666",
            command=self.app.open_recovery_center,
        ).pack(side="left", padx=6)

    def _build_updates_tab(self) -> None:
        card = self._section_card(self._tab_updates, 0, "Updates")
        ctk.CTkLabel(
            card,
            text=(
                "Release checks are surfaced in-app. Use Help when you want to check manually, "
                "open release links, or review troubleshooting notes."
            ),
            justify="left",
            wraplength=760,
            text_color="#c1c7cd",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        ctk.CTkButton(
            card,
            text="Open Help",
            width=120,
            fg_color="#2980b9",
            hover_color="#2471a3",
            command=lambda: self.app._tabview.set("Help"),
        ).grid(row=2, column=0, sticky="w", padx=14, pady=(0, 14))

    def _build_advanced_tab(self) -> None:
        card = self._section_card(self._tab_advanced, 0, "Advanced")
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        ctk.CTkButton(
            actions,
            text="Open App Data",
            width=122,
            fg_color="#555555",
            hover_color="#666666",
            command=self._on_open_data_folder,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Refresh Validation",
            width=138,
            fg_color="#555555",
            hover_color="#666666",
            command=self._on_validate,
        ).pack(side="left", padx=6)

        self._info_box = ctk.CTkTextbox(
            card,
            height=220,
            state="disabled",
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self._info_box.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))

    def _section_card(self, parent, row: int, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent)
        card.grid(row=row, column=0, sticky="ew", padx=8, pady=8)
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(14, 10))
        return card

    def _add_path_row(self, parent, row_index: int, key: str, label: str) -> None:
        ctk.CTkLabel(parent, text=label + ":").grid(row=row_index, column=0, sticky="w", padx=14, pady=4)

        var = self._path_vars.setdefault(key, ctk.StringVar())
        entry = ctk.CTkEntry(parent, textvariable=var)
        entry.grid(row=row_index, column=1, sticky="ew", padx=4, pady=4)

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=row_index, column=2, sticky="w", padx=4, pady=4)
        ctk.CTkButton(actions, text="Browse", width=70, command=lambda k=key: self._browse_path(k)).pack(
            side="left", padx=(0, 4)
        )
        ctk.CTkButton(
            actions,
            text="Open",
            width=56,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda k=key: self._open_path(k),
        ).pack(side="left")

        status = self._status_labels.get(key)
        if status is None:
            status = ctk.CTkLabel(parent, text="-", width=84, anchor="w")
            self._status_labels[key] = status
        status.grid(row=row_index, column=3, padx=(4, 14), pady=4)

    def _populate(self) -> None:
        paths = self.app.paths
        explicit_mapping = {
            "client_root": paths.client_root,
            "server_root": paths.server_root,
            "dedicated_server_root": paths.dedicated_server_root,
            "local_config": paths.local_config,
            "local_save_root": paths.local_save_root,
            "backup_dir": paths.backup_dir,
        }
        self._explicit_path_values = {
            key: str(value) if value else ""
            for key, value in explicit_mapping.items()
        }
        mapping = {
            "client_root": paths.client_root,
            "server_root": paths.server_root,
            "dedicated_server_root": paths.dedicated_server_root,
            "local_config": paths.local_config,
            "local_save_root": paths.dedicated_server_save_root,
            "backup_dir": paths.backup_dir,
        }
        for key, value in mapping.items():
            self._path_vars.setdefault(key, ctk.StringVar())
            self._path_vars[key].set(str(value) if value else "")
        self._refresh_hosted_summary()
        self._on_validate()
        self._info_append("Settings loaded.")

    def refresh_view(self) -> None:
        self._populate()

    def _refresh_hosted_summary(self) -> None:
        for row in self._hosted_profile_rows:
            row.destroy()
        self._hosted_profile_rows.clear()

        profiles = self.app.remote_profiles.list_profiles()
        self._hosted_summary.configure(
            text=f"{len(profiles)} hosted profile(s) configured."
        )

        if not profiles:
            empty = ctk.CTkLabel(
                self._hosted_list,
                text="No hosted profiles yet. Use Manage Hosted Profiles to add one.",
                justify="left",
                wraplength=720,
                text_color="#95a5a6",
            )
            empty.grid(row=0, column=0, sticky="ew", pady=(4, 8))
            self._hosted_profile_rows.append(empty)
            return

        for index, profile in enumerate(profiles):
            row = ctk.CTkFrame(self._hosted_list)
            row.grid(row=index, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                row,
                text=profile.name,
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
            ctk.CTkLabel(
                row,
                text=f"{profile.host}:{profile.port} | {profile.username or '(no username)'}",
                anchor="w",
                text_color="#c1c7cd",
            ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 2))
            ctk.CTkLabel(
                row,
                text=profile.remote_root_dir or "(server folder not set)",
                anchor="w",
                text_color="#95a5a6",
            ).grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
            self._hosted_profile_rows.append(row)

    def _browse_path(self, key: str) -> None:
        folder = filedialog.askdirectory(title=f"Select {key.replace('_', ' ').title()}")
        if folder:
            self._path_vars[key].set(folder)
            self._on_validate()

    def _on_autodetect(self) -> None:
        self._info_append("Running auto-detection...")
        detected = discover_all()
        if detected.client_root:
            self._path_vars["client_root"].set(str(detected.client_root))
        if detected.server_root:
            self._path_vars["server_root"].set(str(detected.server_root))
        if detected.dedicated_server_root:
            self._path_vars["dedicated_server_root"].set(str(detected.dedicated_server_root))
        if detected.local_config:
            self._path_vars["local_config"].set(str(detected.local_config))
        if detected.local_save_root and detected.dedicated_server_root:
            self._path_vars["local_save_root"].set(str(detected.local_save_root))
        self._on_validate()
        self._info_append("Auto-detection complete.")
        log.info("Auto-detection finished")

    def _on_validate(self) -> None:
        validators = {
            "client_root": validate_client_root,
            "server_root": validate_server_root,
            "dedicated_server_root": validate_server_root,
            "local_config": validate_local_config,
        }

        for key, var in self._path_vars.items():
            path_str = var.get().strip()
            label = self._status_labels[key]
            if not path_str:
                label.configure(text="-", text_color="#95a5a6")
                continue

            path = Path(path_str)
            if key in validators:
                valid, _msg = validators[key](path)
                label.configure(
                    text="OK" if valid else "Needs Review",
                    text_color="#2d8a4e" if valid else "#e67e22",
                )
            elif key in {"local_save_root", "backup_dir"}:
                valid = path.is_dir() or path.parent.is_dir()
                label.configure(
                    text="OK" if valid else "Needs Review",
                    text_color="#2d8a4e" if valid else "#e67e22",
                )

    def _on_save(self) -> None:
        paths = self.app.paths
        old_backup_dir = paths.backup_dir

        for key, var in self._path_vars.items():
            value = var.get().strip()
            path_value = self._path_value_for_save(key, value)
            setattr(paths, key, path_value)

        self.app.save_settings()
        if paths.backup_dir != old_backup_dir:
            self.app._rebind_backup_services()
            self.app.refresh_backups_tab()
            self._info_append(f"Rebound backup-backed services to {paths.backup_dir}")

        self._on_validate()
        self._info_append("Settings saved.")
        self.app.refresh_mods_tab()
        self.app.refresh_remote_profile_views()
        self._refresh_hosted_summary()
        messagebox.showinfo("Saved", "Settings saved successfully.")
        log.info("Settings saved")

    def _open_hosted_profile_manager(self) -> None:
        self.app._tabview.set("Server")
        self.app._server_tab.open_hosted_setup()

    def _open_path(self, key: str) -> None:
        path_str = self._path_vars[key].get().strip()
        if not path_str:
            messagebox.showinfo("Not Set", f"{key.replace('_', ' ').title()} is not configured.")
            return
        path = Path(path_str)
        if path.is_dir():
            os.startfile(str(path))
        elif path.is_file():
            os.startfile(str(path.parent))
        else:
            messagebox.showinfo("Not Found", f"Path does not exist:\n{path}")

    def _on_open_data_folder(self) -> None:
        from ..app_window import DEFAULT_DATA_DIR

        if DEFAULT_DATA_DIR.is_dir():
            os.startfile(str(DEFAULT_DATA_DIR))
        else:
            messagebox.showinfo("Not Found", f"Data folder not found:\n{DEFAULT_DATA_DIR}")

    def _path_value_for_save(self, key: str, value: str) -> Path | None:
        if not value:
            return None
        if key != "local_save_root":
            return Path(value)

        explicit_value = self._explicit_path_values.get(key, "")
        effective_root = self.app.paths.dedicated_server_save_root
        effective_value = str(effective_root) if effective_root else ""
        if not explicit_value and value == effective_value:
            return None
        return Path(value)

    def _info_append(self, text: str) -> None:
        try:
            self._info_box.configure(state="normal")
            self._info_box.insert("end", text + "\n")
            self._info_box.see("end")
            self._info_box.configure(state="disabled")
        except Exception:
            pass
