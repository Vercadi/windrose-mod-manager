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

UI_SIZE_LABELS = {
    "Compact": "compact",
    "Default": "default",
    "Large": "large",
}
CONFIRMATION_LABELS = {
    "Always Confirm": "always",
    "Destructive Actions Only": "destructive_only",
    "Reduced Confirmations": "reduced",
    "Disable All Confirmations": "none",
}


class SettingsTab(ctk.CTkFrame):
    def _wrap_length(self, kind: str) -> int:
        tokens = self.app.ui_tokens
        if kind == "header":
            return max(300, tokens.panel_wrap - 120)
        if kind == "detail":
            return tokens.detail_wrap
        return tokens.panel_wrap

    @staticmethod
    def _ui_size_label(value: str) -> str:
        normalized = (value or "default").strip().lower()
        for label, raw in UI_SIZE_LABELS.items():
            if raw == normalized:
                return label
        return "Default"

    @staticmethod
    def _ui_size_value(label: str) -> str:
        return UI_SIZE_LABELS.get((label or "").strip(), "default")

    @staticmethod
    def _confirmation_mode_label(value: str) -> str:
        normalized = (value or "destructive_only").strip().lower()
        for label, raw in CONFIRMATION_LABELS.items():
            if raw == normalized:
                return label
        return "Destructive Actions Only"

    @staticmethod
    def _confirmation_mode_value(label: str) -> str:
        return CONFIRMATION_LABELS.get((label or "").strip(), "destructive_only")

    def __init__(self, master, app: "AppWindow", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._path_vars: dict[str, ctk.StringVar] = {}
        self._status_labels: dict[str, ctk.CTkLabel] = {}
        self._hosted_profile_rows: list[ctk.CTkFrame] = []
        self._explicit_path_values: dict[str, str] = {}
        self._wrap_labels: list[tuple[ctk.CTkLabel, str]] = []
        self._ui_size_var = ctk.StringVar(value=self._ui_size_label(self.app.preferences.ui_size))
        self._confirmation_mode_var = ctk.StringVar(
            value=self._confirmation_mode_label(self.app.preferences.confirmation_mode)
        )
        self._action_buttons: list[ctk.CTkButton] = []

        self._build_header()
        self._build_tabs()
        self._populate()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header,
            text="Settings",
            font=self.app.ui_font("title"),
        ).grid(row=0, column=0, sticky="w", padx=(14, 10), pady=(12, 4))

        self._result_label = ctk.CTkLabel(
            header,
            text="",
            anchor="w",
            justify="left",
            wraplength=self._wrap_length("header"),
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._result_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))

        self._header_hint = ctk.CTkLabel(
            header,
            text=(
                "App-level setup only: client paths, local and dedicated server paths, hosted profiles, "
                "backup storage, and update behavior."
            ),
            anchor="w",
            justify="left",
            wraplength=self._wrap_length("header"),
            text_color="#b7c0c7",
            font=self.app.ui_font("body"),
        )
        self._header_hint.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))
        self._wrap_labels.append((self._header_hint, "header"))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=3, sticky="e", padx=14, pady=10)

        auto_detect = ctk.CTkButton(actions, text="Auto-Detect", width=100, command=self._on_autodetect)
        auto_detect.pack(side="left", padx=(0, 6))
        self._action_buttons.append(auto_detect)
        validate_btn = ctk.CTkButton(
            actions,
            text="Validate",
            width=88,
            fg_color="#555555",
            hover_color="#666666",
            command=self._on_validate,
        )
        validate_btn.pack(side="left", padx=6)
        self._action_buttons.append(validate_btn)
        save_btn = ctk.CTkButton(
            actions,
            text="Save",
            width=88,
            fg_color="#2d8a4e",
            hover_color="#236b3d",
            command=self._on_save,
        )
        save_btn.pack(side="left", padx=(6, 0))
        self._action_buttons.append(save_btn)

    def _build_tabs(self) -> None:
        self._tabs = ctk.CTkTabview(self)
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self._tab_client = self._tabs.add("Client")
        self._tab_server = self._tabs.add("Server")
        self._tab_hosted = self._tabs.add("Hosted")
        self._tab_backups = self._tabs.add("Backups")
        self._tab_updates = self._tabs.add("Updates")
        behavior_tab = self._tabs.add("Behavior")
        self._tab_advanced = self._tabs.add("Advanced")

        for tab in (
            self._tab_client,
            self._tab_server,
            self._tab_hosted,
            self._tab_backups,
            self._tab_updates,
            behavior_tab,
            self._tab_advanced,
        ):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        self._tab_behavior = ctk.CTkScrollableFrame(behavior_tab)
        self._tab_behavior.grid(row=0, column=0, sticky="nsew")
        self._tab_behavior.grid_columnconfigure(0, weight=1)

        self._build_client_tab()
        self._build_server_tab()
        self._build_hosted_tab()
        self._build_backups_tab()
        self._build_updates_tab()
        self._build_behavior_tab()
        self._build_advanced_tab()

    def _build_client_tab(self) -> None:
        card = self._section_card(self._tab_client, 0, "Client")
        self._add_path_row(card, 1, "client_root", "Windrose Client Folder")
        self._add_path_row(card, 2, "local_config", "Local Config Folder")
        self._client_hint = ctk.CTkLabel(
            card,
            text="Launch Windrose uses the client folder configured here.",
            anchor="w",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._client_hint.grid(row=3, column=0, columnspan=4, sticky="ew", padx=14, pady=(2, 14))
        self._wrap_labels.append((self._client_hint, "panel"))

    def _build_server_tab(self) -> None:
        card = self._section_card(self._tab_server, 0, "Server Targets")
        self._add_path_row(card, 1, "server_root", "Local Server Folder (Main Game)")
        self._add_path_row(card, 2, "dedicated_server_root", "Dedicated Server Folder (Steam App)")
        self._add_path_row(card, 3, "local_save_root", "Dedicated Server World Saves Folder")
        self._server_hint = ctk.CTkLabel(
            card,
            text=(
                "Local Server means the bundled server inside the main Windrose game install: "
                "<Windrose>/R5/Builds/WindowsServer. "
                "Dedicated Server means the standalone Steam Windrose Dedicated Server app root, which does not have "
                "the R5/Builds/WindowsServer folder. "
                "Local server world files are derived from <local>/R5/Saved. Dedicated server launch and "
                "dedicated server/world settings use the dedicated server folder, and world saves default to "
                "<dedicated>/R5/Saved."
            ),
            anchor="w",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._server_hint.grid(row=4, column=0, columnspan=4, sticky="ew", padx=14, pady=(2, 14))
        self._wrap_labels.append((self._server_hint, "panel"))

    def _build_hosted_tab(self) -> None:
        card = self._section_card(self._tab_hosted, 0, "Hosted Profiles")
        card.grid(sticky="nsew")
        card.grid_rowconfigure(4, weight=1)
        self._hosted_hint = ctk.CTkLabel(
            card,
            text=(
                "Hosted profiles are app configuration. Use these profiles from the Server screen when you compare, "
                "apply settings, or install to a rented server."
            ),
            anchor="w",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._hosted_hint.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        self._wrap_labels.append((self._hosted_hint, "panel"))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10))
        manage_btn = ctk.CTkButton(
            actions,
            text="Manage Hosted Profiles",
            width=162,
            fg_color="#2980b9",
            hover_color="#2471a3",
            command=self._open_hosted_profile_manager,
        )
        manage_btn.pack(side="left", padx=(0, 6))
        self._action_buttons.append(manage_btn)
        open_server_btn = ctk.CTkButton(
            actions,
            text="Open Server Screen",
            width=138,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: self.app._tabview.set("Server"),
        )
        open_server_btn.pack(side="left", padx=6)
        self._action_buttons.append(open_server_btn)

        self._hosted_summary = ctk.CTkLabel(card, text="", justify="left", text_color="#c1c7cd", font=self.app.ui_font("body"))
        self._hosted_summary.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 8))

        self._hosted_list = ctk.CTkScrollableFrame(card)
        self._hosted_list.grid(row=4, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self._hosted_list.grid_columnconfigure(0, weight=1)

    def _build_backups_tab(self) -> None:
        card = self._section_card(self._tab_backups, 0, "Backups and Activity")
        self._add_path_row(card, 1, "backup_dir", "Backup Storage Folder")
        self._backups_hint = ctk.CTkLabel(
            card,
            text=(
                "Backup copies are created before managed installs and before config writes. "
                "Use Activity & Backups to restore previous versions, undo supported actions, or clean up old backups."
            ),
            anchor="w",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._backups_hint.grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=(2, 10))
        self._wrap_labels.append((self._backups_hint, "panel"))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=3, column=0, columnspan=4, sticky="w", padx=14, pady=(0, 14))
        open_backups_btn = ctk.CTkButton(
            actions, text="Open Backup Storage", width=150, command=lambda: self._open_path("backup_dir")
        )
        open_backups_btn.pack(side="left", padx=(0, 6))
        self._action_buttons.append(open_backups_btn)
        open_recovery_btn = ctk.CTkButton(
            actions,
            text="Open Activity",
            width=124,
            fg_color="#555555",
            hover_color="#666666",
            command=self.app.open_recovery_center,
        )
        open_recovery_btn.pack(side="left", padx=6)
        self._action_buttons.append(open_recovery_btn)

    def _build_updates_tab(self) -> None:
        card = self._section_card(self._tab_updates, 0, "Updates")
        self._updates_hint = ctk.CTkLabel(
            card,
            text=(
                "Release checks are surfaced in-app. Use Help when you want to check manually, "
                "open release links, or review troubleshooting notes."
            ),
            anchor="w",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#c1c7cd",
            font=self.app.ui_font("body"),
        )
        self._updates_hint.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        self._wrap_labels.append((self._updates_hint, "panel"))

        open_help_btn = ctk.CTkButton(
            card,
            text="Open Help",
            width=120,
            fg_color="#2980b9",
            hover_color="#2471a3",
            command=lambda: self.app._tabview.set("Help"),
        )
        open_help_btn.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 14))
        self._action_buttons.append(open_help_btn)

    def _build_behavior_tab(self) -> None:
        card = self._section_card(self._tab_behavior, 0, "Behavior and Readability")
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text="UI Size:",
            font=self.app.ui_font("body"),
        ).grid(row=1, column=0, sticky="w", padx=14, pady=4)
        self._ui_size_menu = ctk.CTkOptionMenu(
            card,
            variable=self._ui_size_var,
            values=list(UI_SIZE_LABELS.keys()),
            width=180,
            font=self.app.ui_font("body"),
            command=self._on_ui_size_changed,
        )
        self._ui_size_menu.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ctk.CTkLabel(
            card,
            text="Confirmation Behavior:",
            font=self.app.ui_font("body"),
        ).grid(row=2, column=0, sticky="w", padx=14, pady=4)
        self._confirmation_menu = ctk.CTkOptionMenu(
            card,
            variable=self._confirmation_mode_var,
            values=list(CONFIRMATION_LABELS.keys()),
            width=180,
            font=self.app.ui_font("body"),
            command=self._on_confirmation_mode_changed,
        )
        self._confirmation_menu.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        self._behavior_result = ctk.CTkLabel(
            card,
            text="",
            anchor="w",
            justify="left",
            wraplength=self._wrap_length("panel"),
            text_color="#c1c7cd",
            font=self.app.ui_font("body"),
        )
        self._behavior_result.grid(row=3, column=0, columnspan=4, sticky="ew", padx=14, pady=(4, 4))
        self._wrap_labels.append((self._behavior_result, "panel"))

        self._behavior_hint = ctk.CTkLabel(
            card,
            text=(
                "Compact fits more rows on screen. Large increases text size across the main workspace while "
                "keeping the same app window size. "
                "Confirmation behavior controls whether routine installs and applies interrupt with popups."
            ),
            anchor="w",
            justify="left",
            wraplength=self._wrap_length("panel"),
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._behavior_hint.grid(row=4, column=0, columnspan=4, sticky="ew", padx=14, pady=(2, 10))
        self._wrap_labels.append((self._behavior_hint, "panel"))

        reset_btn = ctk.CTkButton(
            card,
            text="Reset UI Size to Default",
            width=170,
            fg_color="#555555",
            hover_color="#666666",
            command=self._reset_ui_size,
        )
        reset_btn.grid(row=5, column=0, sticky="w", padx=14, pady=(0, 14))
        self._action_buttons.append(reset_btn)

    def _build_advanced_tab(self) -> None:
        card = self._section_card(self._tab_advanced, 0, "Advanced")
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        open_data_btn = ctk.CTkButton(
            actions,
            text="Open App Data",
            width=122,
            fg_color="#555555",
            hover_color="#666666",
            command=self._on_open_data_folder,
        )
        open_data_btn.pack(side="left", padx=(0, 6))
        self._action_buttons.append(open_data_btn)
        refresh_btn = ctk.CTkButton(
            actions,
            text="Refresh Validation",
            width=138,
            fg_color="#555555",
            hover_color="#666666",
            command=self._on_validate,
        )
        refresh_btn.pack(side="left", padx=6)
        self._action_buttons.append(refresh_btn)

        self._info_box = ctk.CTkTextbox(
            card,
            height=220,
            state="disabled",
            font=self.app.ui_font("mono"),
        )
        self._info_box.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))

    def _section_card(self, parent, row: int, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent)
        card.grid(row=row, column=0, sticky="ew", padx=8, pady=8)
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            card,
            text=title,
            font=self.app.ui_font("card_title"),
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(14, 10))
        return card

    def _add_path_row(self, parent, row_index: int, key: str, label: str) -> None:
        ctk.CTkLabel(parent, text=label + ":", font=self.app.ui_font("body")).grid(
            row=row_index, column=0, sticky="w", padx=14, pady=4
        )

        var = self._path_vars.setdefault(key, ctk.StringVar())
        entry = ctk.CTkEntry(parent, textvariable=var, font=self.app.ui_font("body"))
        entry.grid(row=row_index, column=1, sticky="ew", padx=4, pady=4)

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=row_index, column=2, sticky="w", padx=4, pady=4)
        browse_btn = ctk.CTkButton(actions, text="Browse", width=70, command=lambda k=key: self._browse_path(k))
        browse_btn.pack(side="left", padx=(0, 4))
        self._action_buttons.append(browse_btn)
        open_btn = ctk.CTkButton(
            actions,
            text="Open",
            width=56,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda k=key: self._open_path(k),
        )
        open_btn.pack(side="left")
        self._action_buttons.append(open_btn)

        status = self._status_labels.get(key)
        if status is None:
            status = ctk.CTkLabel(parent, text="-", width=84, anchor="w", font=self.app.ui_font("small"))
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
        self._ui_size_var.set(self._ui_size_label(self.app.preferences.ui_size))
        self._confirmation_mode_var.set(
            self._confirmation_mode_label(self.app.preferences.confirmation_mode)
        )
        self._update_behavior_feedback()
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
                wraplength=self.app.ui_tokens.detail_wrap,
                text_color="#95a5a6",
                font=self.app.ui_font("small"),
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
                font=self.app.ui_font("row_title"),
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
            ctk.CTkLabel(
                row,
                text=f"{profile.host}:{profile.port} | {profile.username or '(no username)'}",
                anchor="w",
                text_color="#c1c7cd",
                font=self.app.ui_font("body"),
            ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 2))
            ctk.CTkLabel(
                row,
                text=profile.remote_root_dir or "(server folder not set)",
                anchor="w",
                text_color="#95a5a6",
                font=self.app.ui_font("small"),
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

        self.app.preferences.ui_size = self._ui_size_value(self._ui_size_var.get())
        self.app.preferences.confirmation_mode = self._confirmation_mode_value(
            self._confirmation_mode_var.get()
        )

        self.app.save_settings()
        if paths.backup_dir != old_backup_dir:
            self.app._rebind_backup_services()
            self.app.refresh_backups_tab()
            self._info_append(f"Rebound backup-backed services to {paths.backup_dir}")

        self.app.refresh_ui_preferences()
        self._on_validate()
        self._info_append("Settings saved.")
        self.app.refresh_mods_tab()
        self.app.refresh_remote_profile_views()
        self._refresh_hosted_summary()
        self._set_result("Settings saved successfully.", level="success")
        self._set_behavior_result("Settings saved. These behavior choices will persist after restart.")
        log.info("Settings saved")

    def _reset_ui_size(self) -> None:
        self._ui_size_var.set("Default")
        self._on_ui_size_changed("Default")

    def _open_hosted_profile_manager(self) -> None:
        self.app._tabview.set("Server")
        self.app._server_tab.open_hosted_setup()

    def _on_ui_size_changed(self, selected: str) -> None:
        label = selected or self._ui_size_var.get()
        self._ui_size_var.set(label)
        self.app.preferences.ui_size = self._ui_size_value(label)
        self.app.refresh_ui_preferences()
        message = f"Previewing {label.lower()} UI size now. The app window size stays the same. Click Save to keep it after restart."
        self._set_result(message, level="info")
        self._set_behavior_result(message)

    def _on_confirmation_mode_changed(self, selected: str) -> None:
        label = selected or self._confirmation_mode_var.get()
        self._confirmation_mode_var.set(label)
        self.app.preferences.confirmation_mode = self._confirmation_mode_value(label)
        descriptions = {
            "Always Confirm": "Routine actions will continue to ask before installing or applying changes.",
            "Destructive Actions Only": "Only destructive or high-risk actions will require confirmation.",
            "Reduced Confirmations": "Routine installs and applies will stay quieter while risky actions still prompt.",
            "Disable All Confirmations": "All confirmation prompts are disabled. Use this only if you prefer speed over safety.",
        }
        message = descriptions.get(label, "Confirmation behavior updated. Click Save to keep it.")
        self._set_result(message, level="info")
        self._set_behavior_result(message)

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

    def _set_result(self, text: str, *, level: str = "info") -> None:
        colors = {
            "success": "#2d8a4e",
            "warning": "#e67e22",
            "error": "#c0392b",
            "info": "#95a5a6",
        }
        self._result_label.configure(text=text, text_color=colors.get(level, "#95a5a6"))

    def _set_behavior_result(self, text: str) -> None:
        self._behavior_result.configure(text=text)

    def _update_behavior_feedback(self) -> None:
        size_label = self._ui_size_var.get() or "Default"
        confirm_label = self._confirmation_mode_var.get() or "Destructive Actions Only"
        self._set_behavior_result(
            f"Current preview: {size_label} UI. Confirmation mode: {confirm_label}. Click Save to keep these choices."
        )

    def apply_ui_preferences(self) -> None:
        tokens = self.app.ui_tokens
        self._result_label.configure(font=self.app.ui_font("small"), wraplength=self._wrap_length("header"))
        self._ui_size_menu.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height)
        self._confirmation_menu.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height)
        for label, wrap_kind in self._wrap_labels:
            try:
                label.configure(wraplength=self._wrap_length(wrap_kind))
            except Exception:
                pass
        for button in self._action_buttons:
            try:
                button.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height)
            except Exception:
                pass
        self._hosted_summary.configure(font=self.app.ui_font("body"))
        self._behavior_result.configure(font=self.app.ui_font("body"))
        self._info_box.configure(font=self.app.ui_font("mono"))
