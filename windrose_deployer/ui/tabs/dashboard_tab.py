"""Dashboard tab for operational overview."""
from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from urllib.request import urlopen

import customtkinter as ctk

from ...core.archive_inspector import inspect_archive
from ...core.conflict_detector import check_plan_conflicts
from ...core.framework_config_service import KNOWN_CONFIGS
from ...core.remote_deployer import plan_remote_deployment
from ...models.mod_install import InstallTarget


_COMPARE_TARGETS = {
    "Local Server": "server",
    "Dedicated Server": "dedicated_server",
    "Hosted Server": "hosted",
}


class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, *, app):
        super().__init__(master)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._action_buttons: list[ctk.CTkButton] = []
        self._status_values: dict[str, ctk.CTkLabel] = {}
        self._setup_values: dict[str, ctk.CTkLabel] = {}
        self._count_values: dict[str, ctk.CTkLabel] = {}
        self._framework_values: dict[str, ctk.CTkLabel] = {}
        self._compare_target_var = ctk.StringVar(value="Dedicated Server")
        self._build()

    def _build(self) -> None:
        body = ctk.CTkScrollableFrame(self)
        body.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self._title = ctk.CTkLabel(body, text="Dashboard", font=self.app.ui_font("title"))
        self._title.grid(row=0, column=0, sticky="w", padx=8, pady=(0, 2))
        self._refresh_btn = ctk.CTkButton(
            body,
            text="Refresh",
            width=92,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._manual_refresh,
        )
        self._refresh_btn.grid(row=0, column=1, sticky="e", padx=8, pady=(0, 2))

        self._subtitle = ctk.CTkLabel(
            body,
            text="Operations home for Windrose client, local server, dedicated server, and hosted server state.",
            justify="left",
            anchor="w",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._subtitle.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 10))

        self._status_card = self._make_card(body, row=2, column=0, title="Status")
        self._current_card = self._make_card(body, row=2, column=1, title="Current Setup")
        self._frameworks_card = self._make_card(body, row=3, column=0, title="Frameworks")
        self._parity_card = self._make_card(body, row=3, column=1, title="Mod Parity")
        self._actions_card = self._make_card(body, row=4, column=0, title="Quick Actions", columnspan=2)

        self._build_status_card()
        self._build_current_card()
        self._build_frameworks_card()
        self._build_parity_card()
        self._build_actions_card()

    def _make_card(self, body, *, row: int, column: int, title: str, columnspan: int = 1):
        card = ctk.CTkFrame(body)
        padx = 8 if columnspan > 1 else (8 if column == 0 else (4, 8))
        card.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=padx, pady=(0, 6))
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text=title, font=self.app.ui_font("card_title")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6)
        )
        return card

    def _build_status_card(self) -> None:
        labels = [
            ("client", "Windrose Client"),
            ("server", "Local Server"),
            ("dedicated_server", "Dedicated Server"),
            ("hosted", "Hosted Server"),
        ]
        for index, (key, label) in enumerate(labels, start=1):
            ctk.CTkLabel(
                self._status_card,
                text=label,
                font=self.app.ui_font("body"),
                text_color="#aeb6bf",
            ).grid(row=index, column=0, sticky="w", padx=12, pady=2)
            value = ctk.CTkLabel(self._status_card, text="", anchor="e", font=self.app.ui_font("body"))
            value.grid(row=index, column=1, sticky="e", padx=12, pady=2)
            self._status_values[key] = value

    def _build_frameworks_card(self) -> None:
        labels = [
            ("ue4ss", "UE4SS Runtime"),
            ("rcon", "RCON"),
            ("windrose_plus", "WindrosePlus"),
        ]
        for index, (key, label) in enumerate(labels, start=1):
            ctk.CTkLabel(
                self._frameworks_card,
                text=label,
                font=self.app.ui_font("body"),
                text_color="#aeb6bf",
            ).grid(row=index, column=0, sticky="w", padx=12, pady=3)
            value = ctk.CTkLabel(
                self._frameworks_card,
                text="",
                anchor="w",
                justify="left",
                font=self.app.ui_font("body"),
                wraplength=self.app.ui_tokens.detail_wrap,
            )
            value.grid(row=index, column=1, sticky="ew", padx=12, pady=3)
            self._framework_values[key] = value

        self._framework_note = ctk.CTkLabel(
            self._frameworks_card,
            text="WindrosePlus uses its own install/start workflow.",
            justify="left",
            anchor="w",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
            wraplength=self.app.ui_tokens.panel_wrap,
        )
        self._framework_note.grid(row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=(2, 6))
        ctk.CTkButton(
            self._frameworks_card,
            text="Manage Frameworks",
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._open_frameworks_dialog,
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))

    def _build_current_card(self) -> None:
        labels = [
            ("source", "Active Source"),
            ("world", "Active World"),
            ("profile", "Hosted Profile"),
            ("apply", "Last Apply"),
            ("restart", "Last Restart"),
            ("backup", "Last Backup"),
        ]
        for index, (key, label) in enumerate(labels, start=1):
            ctk.CTkLabel(
                self._current_card,
                text=label,
                font=self.app.ui_font("body"),
                text_color="#aeb6bf",
            ).grid(row=index, column=0, sticky="w", padx=12, pady=3)
            value = ctk.CTkLabel(
                self._current_card,
                text="",
                justify="left",
                anchor="e",
                font=self.app.ui_font("body"),
                wraplength=self.app.ui_tokens.panel_wrap - 40,
            )
            value.grid(row=index, column=1, sticky="e", padx=12, pady=3)
            self._setup_values[key] = value

    def _build_parity_card(self) -> None:
        ctk.CTkLabel(
            self._parity_card,
            text="Compare Target",
            font=self.app.ui_font("body"),
            text_color="#aeb6bf",
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 6))
        self._compare_target_menu = ctk.CTkOptionMenu(
            self._parity_card,
            variable=self._compare_target_var,
            values=list(_COMPARE_TARGETS.keys()),
            width=170,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
        )
        self._compare_target_menu.grid(row=1, column=1, sticky="e", padx=14, pady=(0, 6))

        self._parity_state = ctk.CTkLabel(
            self._parity_card,
            text="",
            anchor="w",
            font=self.app.ui_font("row_title"),
        )
        self._parity_state.grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 4))

        self._parity_summary = ctk.CTkLabel(
            self._parity_card,
            text="",
            justify="left",
            anchor="w",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
            wraplength=self.app.ui_tokens.panel_wrap,
        )
        self._parity_summary.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))

        self._drift_label = ctk.CTkLabel(
            self._parity_card,
            text="",
            justify="left",
            anchor="w",
            text_color="#e67e22",
            font=self.app.ui_font("small"),
            wraplength=self.app.ui_tokens.panel_wrap,
        )
        self._drift_label.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))

        button_bar = ctk.CTkFrame(self._parity_card, fg_color="transparent")
        button_bar.grid(row=5, column=0, columnspan=2, sticky="ew", padx=14, pady=(2, 8))
        button_bar.grid_columnconfigure(0, weight=1)
        button_bar.grid_columnconfigure(1, weight=1)

        self._compare_btn = ctk.CTkButton(
            button_bar,
            text="Run Compare",
            width=126,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=self._run_compare,
        )
        self._compare_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 4))
        self._action_buttons.append(self._compare_btn)
        self._open_compare_btn = ctk.CTkButton(
            button_bar,
            text="Open Full Compare",
            width=146,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._open_full_compare,
        )
        self._open_compare_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 4))
        self._action_buttons.append(self._open_compare_btn)
        self._review_sync_btn = ctk.CTkButton(
            button_bar,
            text="Review Sync Actions",
            width=170,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            state="disabled",
            command=self._review_sync_actions,
        )
        self._review_sync_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self._action_buttons.append(self._review_sync_btn)

        labels = [
            ("client", "Client"),
            ("server", "Local Server"),
            ("dedicated_server", "Dedicated Server"),
            ("hosted", "Hosted Server"),
        ]
        for index, (key, label) in enumerate(labels, start=6):
            ctk.CTkLabel(
                self._parity_card,
                text=label,
                font=self.app.ui_font("body"),
                text_color="#aeb6bf",
            ).grid(row=index, column=0, sticky="w", padx=14, pady=4)
            value = ctk.CTkLabel(self._parity_card, text="0", anchor="e", font=self.app.ui_font("body"))
            value.grid(row=index, column=1, sticky="e", padx=14, pady=4)
            self._count_values[key] = value

    def _build_actions_card(self) -> None:
        actions = ctk.CTkFrame(self._actions_card, fg_color="transparent")
        actions.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=14, pady=(0, 14))
        for column in range(4):
            actions.grid_columnconfigure(column, weight=1)

        self._add_action_button(
            actions, row=0, column=0, text="Launch Windrose", command=self.app._on_start_game,
            fg="#2d8a4e", hover="#236b3d",
        )
        self._add_action_button(
            actions, row=0, column=1, text="Launch Dedicated Server", command=self.app._on_start_server,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=0, column=2, text="Open Server Folder", command=self.app._server_tab._open_active_server_folder,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=0, column=3, text="Back Up Now", command=self.app._server_tab._on_backup_now,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=1, column=0, text="Open Client Mods", command=self._open_client_mods_folder,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=1, column=1, text="Open Local Server Mods", command=self._open_local_server_mods_folder,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=1, column=2, text="Open Dedicated Server Mods", command=self._open_dedicated_server_mods_folder,
            fg="#555555", hover="#666666",
        )

    def _manual_refresh(self) -> None:
        self.refresh_view()
        self._subtitle.configure(
            text=f"Operations home for Windrose client, local server, dedicated server, and hosted server state. Last refreshed {datetime.now().strftime('%H:%M:%S')}."
        )

    def _add_action_button(self, parent, *, row: int, column: int, text: str, command, fg: str, hover: str) -> None:
        button = ctk.CTkButton(
            parent,
            text=text,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color=fg,
            hover_color=hover,
            command=command,
        )
        button.grid(row=row, column=column, sticky="ew", padx=4, pady=4)
        self._action_buttons.append(button)

    def _open_frameworks_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Frameworks")
        self.app.center_dialog(dialog, 900, 680)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(dialog, text="Frameworks", font=self.app.ui_font("title")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 4)
        )
        ctk.CTkLabel(
            dialog,
            text="Known UE4SS, RCON, and WindrosePlus actions only. These actions do not edit arbitrary files.",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
            wraplength=820,
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        control_row = ctk.CTkFrame(dialog, fg_color="transparent")
        control_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        ctk.CTkLabel(control_row, text="Target:", font=self.app.ui_font("body")).pack(side="left")
        target_var = ctk.StringVar(value=self._default_framework_target_label())
        content = ctk.CTkScrollableFrame(dialog)
        content.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 8))
        content.grid_columnconfigure(0, weight=1)
        result_label = ctk.CTkLabel(dialog, text="", font=self.app.ui_font("small"), text_color="#95a5a6")
        result_label.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 14))

        def set_result(text: str, color: str = "#95a5a6") -> None:
            result_label.configure(text=text, text_color=color)

        def render(_choice: str | None = None) -> None:
            for widget in content.winfo_children():
                widget.destroy()
            root = self._framework_target_root(target_var.get())
            state = self.app.framework_state.local_state(root)
            self._render_framework_dialog_content(content, target_var.get(), root, state, set_result, refresh_content=render)

        ctk.CTkOptionMenu(
            control_row,
            values=["Client", "Local Server", "Dedicated Server"],
            variable=target_var,
            command=render,
            width=220,
            font=self.app.ui_font("body"),
        ).pack(side="left", padx=(8, 0))
        render()

    def _render_framework_dialog_content(self, parent, target_label: str, root: Path | None, state, set_result, refresh_content=None) -> None:
        if root is None:
            self._framework_section(parent, "Target", [f"{target_label} is not configured in Settings."], [])
            return

        ue4ss_actions = []
        if self._known_config_exists(root, "ue4ss_settings"):
            ue4ss_actions.append(("Edit UE4SS Settings", lambda r=root: self._open_known_config_editor(r, "ue4ss_settings", set_result)))
        ue4ss_actions.append(("Repair / Reinstall Runtime", lambda r=root, t=target_label: self._repair_ue4ss_runtime(r, t, set_result)))
        self._framework_section(
            parent,
            "UE4SS Runtime",
            [
                f"Status: {'Installed' if state.ue4ss_runtime else 'Missing'}" + (" (partial)" if state.ue4ss_partial else ""),
                "Runtime path: R5\\Binaries\\Win64",
                "UE4SS-settings.ini changes require a restart." if state.ue4ss_runtime else "Install or repair the runtime before editing runtime settings.",
            ],
            ue4ss_actions,
        )

        if target_label == "Client":
            client_rcon_status = "Detected on Client - unsupported" if state.rcon_mod else "Not installed"
            self._framework_section(
                parent,
                "RCON",
                [
                    f"Status: {client_rcon_status}",
                    "RCON is server-only. Install and configure it on Local Server or Dedicated Server, not Client.",
                    "If RCON files are present in the client folder, remove them unless you are deliberately testing an unsupported setup.",
                ],
                [],
            )
        else:
            rcon_status = "Not installed"
            if state.rcon_mod:
                rcon_status = "Installed, password needs review" if state.rcon_missing_password else "Installed"
            self._framework_section(
                parent,
                "RCON",
                [
                    f"Status: {rcon_status}",
                    "RCON is server-side and installs version.dll to R5\\Binaries\\Win64. Client installs are blocked.",
                    "Start the server once to generate windrosercon\\settings.ini, then configure port/password.",
                    "Live RCON admin/test commands are deferred until the protocol path is proven reliable.",
                ],
                [("Edit RCON Settings", lambda r=root: self._open_rcon_settings_editor(r, set_result))] if state.rcon_configured else [],
            )

        wp_paths = self.app.framework_config.windrose_plus_paths(root)
        wp_actions = []
        if wp_paths and wp_paths.install_script.is_file():
            wp_actions.append(("Run WindrosePlus Install", lambda r=root: self._run_windrose_plus_install(r, set_result, refresh_content)))
        if wp_paths and wp_paths.folder.exists():
            wp_actions.append(("Open WindrosePlus Folder", lambda p=wp_paths.folder: self._open_existing_path(p, set_result)))
        if self._known_config_exists(root, "windrose_plus_json"):
            wp_actions.append(("Edit windrose_plus.json", lambda r=root: self._open_known_config_editor(r, "windrose_plus_json", set_result)))
        if self._any_windrose_plus_ini_exists(root):
            wp_actions.append(("Edit Override INI...", lambda r=root: self._open_windrose_plus_ini_picker(r, set_result)))
        if wp_paths and wp_paths.dashboard_launcher.is_file():
            wp_actions.append(("Open WindrosePlus Dashboard", lambda r=root: self._open_windrose_plus_dashboard(r, set_result)))
        if wp_paths and wp_paths.build_script.is_file():
            wp_actions.append(("Rebuild WindrosePlus Overrides", lambda r=root: self._run_windrose_plus_rebuild(r, set_result, refresh_content)))
        if wp_paths and wp_paths.launch_wrapper.is_file():
            wp_actions.append(("Launch WindrosePlus Server", lambda: self._launch_windrose_plus_server(set_result)))
        self._framework_section(
            parent,
            "WindrosePlus",
            [
                f"Package files: {'present' if state.windrose_plus_package else 'missing'}",
                f"Active UE4SS mod: {'present' if state.windrose_plus else 'missing'}",
                f"Generated PAKs: {'present' if state.windrose_plus_generated_paks else 'not generated'}",
                f"Launch wrapper: {'present' if state.windrose_plus_launch_wrapper else 'missing'}",
                "Generated PAKs are only expected after multiplier or override changes.",
                "Override .ini changes require Rebuild WindrosePlus Overrides before launch.",
            ],
            wp_actions,
        )

    def _framework_section(self, parent, title: str, lines: list[str], actions: list[tuple[str, object]]) -> None:
        row = len(parent.winfo_children())
        card = ctk.CTkFrame(parent)
        card.grid(row=row, column=0, sticky="ew", padx=4, pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 4)
        )
        ctk.CTkLabel(
            card,
            text="\n".join(lines),
            justify="left",
            anchor="w",
            text_color="#c1c7cd",
            font=self.app.ui_font("small"),
            wraplength=780,
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        if actions:
            action_row = ctk.CTkFrame(card, fg_color="transparent")
            action_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 12))
            for index, (label, command) in enumerate(actions):
                action_row.grid_columnconfigure(index % 3, weight=1)
                ctk.CTkButton(
                    action_row,
                    text=label,
                    height=self.app.ui_tokens.compact_button_height,
                    font=self.app.ui_font("body"),
                    fg_color="#555555",
                    hover_color="#666666",
                    command=command,
                ).grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=4)

    def _default_framework_target_label(self) -> str:
        if self.app.paths.dedicated_server_root:
            return "Dedicated Server"
        if self.app.paths.server_root:
            return "Local Server"
        return "Client"

    def _framework_target_root(self, label: str) -> Path | None:
        return {
            "Client": self.app.paths.client_root,
            "Local Server": self.app.paths.server_root,
            "Dedicated Server": self.app.paths.dedicated_server_root,
        }.get(label)

    def _framework_target_preset(self, label: str) -> str:
        return {"Client": "client", "Local Server": "local", "Dedicated Server": "dedicated"}.get(label, "dedicated")

    def _known_config_exists(self, root: Path, key: str) -> bool:
        path = self.app.framework_config.config_path(root, key)
        return bool(path and path.is_file())

    def _any_windrose_plus_ini_exists(self, root: Path) -> bool:
        keys = [
            "windrose_plus_ini",
            "windrose_plus_food_ini",
            "windrose_plus_weapons_ini",
            "windrose_plus_gear_ini",
            "windrose_plus_entities_ini",
        ]
        return any(self._known_config_exists(root, key) for key in keys)

    def _open_known_config_editor(self, root: Path, key: str, set_result) -> None:
        spec = KNOWN_CONFIGS.get(key)
        if spec is None:
            set_result("Unknown config file.", "#c0392b")
            return
        path, text = self.app.framework_config.read_config(root, key)
        if path is None:
            set_result("Target root is not configured.", "#c0392b")
            return
        self._open_text_editor(
            title=spec.label,
            path=path,
            text=text,
            guidance=spec.guidance,
            on_save=lambda new_text: self.app.framework_config.save_config(root, key, new_text),
            set_result=set_result,
        )

    def _open_rcon_settings_editor(self, root: Path, set_result) -> None:
        existing = self.app.rcon_config_svc.load_local(root)
        dialog = ctk.CTkToplevel(self)
        dialog.title("WindroseRCON Settings")
        self.app.center_dialog(dialog, 440, 260)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="WindroseRCON settings.ini", font=self.app.ui_font("card_title")).pack(
            anchor="w", padx=16, pady=(16, 6)
        )
        ctk.CTkLabel(
            dialog,
            text="Known fields only. Save creates a backup first; restart/reload the server mod after saving.",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
            wraplength=390,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        port_var = ctk.StringVar(value=str(existing.port if existing else 27065))
        password_var = ctk.StringVar(value=existing.password if existing else "")
        enabled_var = tk.BooleanVar(value=bool(existing.enabled if existing else True))
        for label, var in (("Port", port_var), ("Password", password_var)):
            row = ctk.CTkFrame(dialog, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(row, text=label, width=90, anchor="w", font=self.app.ui_font("body")).pack(side="left")
            ctk.CTkEntry(row, textvariable=var, font=self.app.ui_font("body")).pack(side="left", fill="x", expand=True)
        ctk.CTkCheckBox(dialog, text="Enabled", variable=enabled_var, font=self.app.ui_font("body")).pack(
            anchor="w", padx=16, pady=(4, 10)
        )

        def save() -> None:
            try:
                from ...core.rcon_config_service import RconSettings

                settings = RconSettings(port=int(port_var.get().strip()), password=password_var.get(), enabled=enabled_var.get())
                self.app.rcon_config_svc.save_local(root, settings)
                set_result("Saved WindroseRCON settings. Restart/reload recommended.", "#2d8a4e")
                self.refresh_view()
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Save Failed", str(exc))

        button_row = ctk.CTkFrame(dialog, fg_color="transparent")
        button_row.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(button_row, text="Save", width=100, command=save).pack(side="left")
        ctk.CTkButton(button_row, text="Cancel", width=100, fg_color="#555555", hover_color="#666666", command=dialog.destroy).pack(side="right")

    def _open_text_editor(self, *, title: str, path: Path, text: str, guidance: str, on_save, set_result) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        self.app.center_dialog(dialog, 820, 620)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(dialog, text=title, font=self.app.ui_font("card_title")).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            dialog,
            text=f"{path}\n{guidance}",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
            justify="left",
            wraplength=760,
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        box = ctk.CTkTextbox(dialog, font=self.app.ui_font("mono_small"))
        box.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        box.insert("1.0", text)
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))

        def save() -> None:
            try:
                saved_path = on_save(box.get("1.0", "end-1c"))
                set_result(f"Saved {saved_path.name}. Backup created if the file already existed.", "#2d8a4e")
                self.refresh_view()
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Save Failed", str(exc))

        ctk.CTkButton(buttons, text="Save", width=100, command=save).pack(side="left")
        ctk.CTkButton(buttons, text="Cancel", width=100, fg_color="#555555", hover_color="#666666", command=dialog.destroy).pack(side="right")

    def _open_windrose_plus_ini_picker(self, root: Path, set_result) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("WindrosePlus Override INI")
        self.app.center_dialog(dialog, 420, 300)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Choose override file", font=self.app.ui_font("card_title")).pack(anchor="w", padx=16, pady=(16, 8))
        keys = [
            "windrose_plus_ini",
            "windrose_plus_food_ini",
            "windrose_plus_weapons_ini",
            "windrose_plus_gear_ini",
            "windrose_plus_entities_ini",
        ]
        for key in keys:
            spec = KNOWN_CONFIGS[key]
            ctk.CTkButton(
                dialog,
                text=spec.label,
                height=self.app.ui_tokens.compact_button_height,
                font=self.app.ui_font("body"),
                command=lambda current=key: (dialog.destroy(), self._open_known_config_editor(root, current, set_result)),
            ).pack(fill="x", padx=16, pady=4)

    def _repair_ue4ss_runtime(self, _root: Path, target_label: str, set_result) -> None:
        entry = next(
            (
                item for item in self.app._mods_tab.library_entries()
                if item.get("install_kind") == "ue4ss_runtime" and Path(str(item.get("path", ""))).is_file()
            ),
            None,
        )
        if entry is None:
            set_result("No UE4SS runtime source archive is available in Inactive Mods.", "#e67e22")
            return
        archive_path = Path(str(entry["path"]))
        if not self.app.confirm_action("routine", "Repair UE4SS Runtime", f"Install/repair UE4SS runtime from:\n{archive_path.name}"):
            return
        self.app._mods_tab._install_path_with_preset(archive_path, self._framework_target_preset(target_label))
        self.refresh_view()
        set_result("UE4SS runtime repair/install started from the available source archive.", "#2d8a4e")

    def _run_windrose_plus_install(self, root: Path, set_result, refresh_content=None) -> None:
        if not self.app.confirm_action("destructive", "Run WindrosePlus Install", "Run WindrosePlus install.ps1 for this server root?"):
            return
        self._run_framework_worker(lambda: self.app.framework_config.run_windrose_plus_install(root), "WindrosePlus install", set_result, refresh_content=refresh_content)

    def _run_windrose_plus_rebuild(self, root: Path, set_result, refresh_content=None) -> None:
        if not self.app.confirm_action("destructive", "Rebuild WindrosePlus Overrides", "Run WindrosePlus-BuildPak.ps1 -RemoveStalePak for this server root?"):
            return
        self._run_framework_worker(lambda: self.app.framework_config.run_windrose_plus_rebuild(root), "WindrosePlus rebuild", set_result, refresh_content=refresh_content)

    def _launch_windrose_plus_server(self, set_result) -> None:
        if self.app._on_start_windrose_plus_server():
            set_result("WindrosePlus server launch started.", "#2d8a4e")
            self.refresh_view()
        else:
            set_result("WindrosePlus server launch failed. Check the dedicated server root and launcher file.", "#c0392b")

    def _run_framework_worker(self, work, label: str, set_result, refresh_content=None) -> None:
        set_result(f"{label} running...", "#95a5a6")

        def thread_main() -> None:
            try:
                completed = work()
                output = (completed.stdout or completed.stderr or "").strip()
                message = f"{label} finished with exit code {completed.returncode}."
                if output:
                    message += f"\n\n{output[-1200:]}"
                color = "#2d8a4e" if completed.returncode == 0 else "#e67e22"
            except Exception as exc:
                message = f"{label} failed: {exc}"
                color = "#c0392b"

            def _finish() -> None:
                set_result(message, color)
                self.refresh_view()
                if callable(refresh_content):
                    refresh_content()

            self.app.dispatch_to_ui(_finish)

        threading.Thread(target=thread_main, daemon=True).start()

    def _open_existing_path(self, path: Path | None, set_result) -> None:
        if path is None or not path.exists():
            set_result("Path is not available for this target.", "#e67e22")
            return
        subprocess.Popen(["explorer", str(path if path.is_dir() else path.parent)])

    def _open_windrose_plus_dashboard(self, root: Path, set_result) -> None:
        paths = self.app.framework_config.windrose_plus_paths(root)
        url = self._windrose_plus_dashboard_url(root)
        if self._dashboard_url_ready(url):
            set_result(f"WindrosePlus dashboard is already running. Opening {url}.", "#2d8a4e")
            webbrowser.open(url)
            return
        if paths and paths.dashboard_launcher.is_file():
            subprocess.Popen(
                ["cmd.exe", "/k", "call", str(paths.dashboard_launcher)],
                cwd=str(paths.dashboard_launcher.parent),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            set_result(f"Started WindrosePlus dashboard launcher. Opening {url} shortly.", "#2d8a4e")
            self.after(1800, lambda: webbrowser.open(url))
        else:
            set_result(f"WindrosePlus dashboard launcher was not found. Opening {url} only.", "#e67e22")
            webbrowser.open(url)

    def _windrose_plus_dashboard_url(self, root: Path) -> str:
        config_path = root / "windrose_plus.json"
        port = 8780
        if config_path.is_file():
            try:
                import json

                data = json.loads(config_path.read_text(encoding="utf-8", errors="replace"))
                port = int(data.get("server", {}).get("http_port", port))
            except Exception:
                port = 8780
        return f"http://localhost:{port}/"

    @staticmethod
    def _dashboard_url_ready(url: str) -> bool:
        try:
            with urlopen(url, timeout=0.35):
                return True
        except Exception:
            return False

    def _run_compare(self) -> None:
        self._set_server_target_from_dashboard(refresh_inventory=False)
        self.app._server_tab.compare_now()

    def _open_full_compare(self) -> None:
        self._set_server_target_from_dashboard(refresh_inventory=False)
        self.app._tabview.set("Server")
        self.app._on_tab_changed("Server")

    def _dashboard_target_key(self) -> str:
        return _COMPARE_TARGETS.get(self._compare_target_var.get(), "dedicated_server")

    def _set_server_target_from_dashboard(self, *, refresh_inventory: bool = False) -> str:
        target = self._dashboard_target_key()
        self.app._server_tab.set_source_for_compare(target, refresh_inventory=refresh_inventory)
        return target

    def _review_sync_actions(self) -> None:
        target = self._set_server_target_from_dashboard(refresh_inventory=False)
        server_tab = self.app._server_tab
        if server_tab.last_compare_target() != target or server_tab.last_compare_report() is None:
            messagebox.showinfo("Run Compare First", "Run Compare for the selected target before reviewing sync actions.")
            return
        if server_tab.last_compare_report().review_needed == 0:
            messagebox.showinfo("No Sync Actions", "The last compare did not find any differences that need review.")
            return

        if target == "hosted":
            profile = server_tab._selected_remote_profile()
            if profile is None:
                messagebox.showwarning("Hosted Profile Required", "Choose a hosted profile first.")
                return
            self._review_sync_btn.configure(state="disabled", text="Checking Hosted...")

            def _work() -> None:
                try:
                    remote_files = self.app.remote_deployer.list_remote_files(profile)
                    self.app.dispatch_to_ui(
                        lambda: self._open_sync_review_dialog(target, remote_files=remote_files)
                    )
                except Exception as exc:
                    self.app.dispatch_to_ui(
                        lambda error=str(exc): messagebox.showerror("Hosted Sync Review Failed", error)
                    )
                finally:
                    def _restore_review_button() -> None:
                        if self._review_sync_btn.winfo_exists():
                            self._review_sync_btn.configure(text="Review Sync Actions")
                            self.refresh_view()
                    self.app.dispatch_to_ui(_restore_review_button)

            threading.Thread(target=_work, daemon=True).start()
            return

        self._open_sync_review_dialog(target)

    def _open_sync_review_dialog(self, target: str, *, remote_files: list[str] | None = None) -> None:
        actions, notes = self._build_sync_review_actions(target, remote_files=remote_files or [])
        dialog = ctk.CTkToplevel(self)
        dialog.title("Review Sync Actions")
        self.app.center_dialog(dialog, 760, 560)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)

        target_label = self._target_label(target)
        ctk.CTkLabel(
            dialog,
            text=f"Review Sync Actions: Client -> {target_label}",
            font=self.app.ui_font("detail_title"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            dialog,
            text=(
                "Only safe additive actions are checked by default. "
                "Server-only removals and ambiguous items are listed for review, not applied automatically."
            ),
            text_color="#95a5a6",
            justify="left",
            wraplength=700,
            font=self.app.ui_font("body"),
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        list_frame = ctk.CTkScrollableFrame(dialog)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        list_frame.grid_columnconfigure(1, weight=1)

        action_vars: list[tuple[dict, tk.BooleanVar]] = []
        row = 0
        if actions:
            for action in actions:
                var = tk.BooleanVar(value=bool(action["enabled"]))
                checkbox = ctk.CTkCheckBox(
                    list_frame,
                    text="",
                    variable=var,
                    state="normal" if action["enabled"] else "disabled",
                    width=24,
                )
                checkbox.grid(row=row, column=0, sticky="nw", padx=(8, 4), pady=(8, 2))
                title = action["title"]
                detail = action["detail"] if action["enabled"] else f"{action['detail']} | {action['reason']}"
                ctk.CTkLabel(
                    list_frame,
                    text=title,
                    font=self.app.ui_font("row_title"),
                    anchor="w",
                    justify="left",
                ).grid(row=row, column=1, sticky="ew", padx=4, pady=(8, 0))
                ctk.CTkLabel(
                    list_frame,
                    text=detail,
                    text_color="#95a5a6" if action["enabled"] else "#e67e22",
                    font=self.app.ui_font("small"),
                    anchor="w",
                    justify="left",
                    wraplength=640,
                ).grid(row=row + 1, column=1, sticky="ew", padx=4, pady=(0, 8))
                action_vars.append((action, var))
                row += 2
        else:
            ctk.CTkLabel(
                list_frame,
                text="No safe install/upload actions were found for this compare.",
                text_color="#95a5a6",
                font=self.app.ui_font("body"),
            ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=8)
            row += 1

        if notes:
            ctk.CTkLabel(
                list_frame,
                text="Review Separately",
                font=self.app.ui_font("row_title"),
            ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(12, 4))
            row += 1
            for note in notes:
                ctk.CTkLabel(
                    list_frame,
                    text=note,
                    text_color="#e67e22",
                    justify="left",
                    anchor="w",
                    wraplength=700,
                    font=self.app.ui_font("small"),
                ).grid(row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=2)
                row += 1

        status = ctk.CTkLabel(dialog, text="", text_color="#95a5a6", justify="left", wraplength=700)
        status.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 8))
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 16))

        def _apply_selected() -> None:
            selected = [action for action, var in action_vars if action["enabled"] and var.get()]
            if not selected:
                status.configure(text="Select at least one safe action first.", text_color="#e67e22")
                return
            apply_btn.configure(state="disabled", text="Applying...")
            if target == "hosted":
                self._apply_hosted_sync_actions(selected, dialog, status, apply_btn)
            else:
                self._apply_local_sync_actions(selected, target, dialog, status, apply_btn)

        apply_btn = ctk.CTkButton(
            buttons,
            text="Apply Selected",
            width=130,
            fg_color="#2d8a4e",
            hover_color="#236b3d",
            command=_apply_selected,
            state="normal" if any(action["enabled"] for action in actions) else "disabled",
        )
        apply_btn.pack(side="left")
        ctk.CTkButton(
            buttons,
            text="Open Full Compare",
            width=140,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: (dialog.destroy(), self._open_full_compare()),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            buttons,
            text="Close",
            width=100,
            fg_color="#444444",
            hover_color="#555555",
            command=dialog.destroy,
        ).pack(side="right")

    def _build_sync_review_actions(self, target: str, *, remote_files: list[str]) -> tuple[list[dict], list[str]]:
        mods = self.app.manifest.list_mods()
        notes: list[str] = []
        actions: list[dict] = []
        if target == "hosted":
            missing = self.app.server_sync.client_mods_missing_from_hosted(mods, remote_files)
            server_only = self.app.server_sync.hosted_files_missing_from_client(mods, remote_files)
            for file_name in server_only[:25]:
                notes.append(f"{file_name}: hosted-only file. Review before deleting; no automatic removal is selected.")
            if len(server_only) > 25:
                notes.append(f"{len(server_only) - 25} more hosted-only file(s) omitted from this preview.")
        else:
            missing = self.app.server_sync.client_mods_missing_from_local(mods, target=target)
            server_only_mods = self.app.server_sync.server_mods_missing_from_client(mods, target=target)
            for mod in server_only_mods[:25]:
                notes.append(f"{mod.display_name}: installed on {self._target_label(target)} only. Review before uninstalling.")
            if len(server_only_mods) > 25:
                notes.append(f"{len(server_only_mods) - 25} more server-only mod(s) omitted from this preview.")

        for mod in missing:
            action = self._build_sync_action_for_mod(mod, target)
            actions.append(action)

        return actions, notes

    def _build_sync_action_for_mod(self, mod, target: str) -> dict:
        target_label = self._target_label(target)
        archive = Path(mod.source_archive) if mod.source_archive else None
        base = {
            "mod_id": mod.mod_id,
            "name": mod.display_name,
            "target": target,
            "title": f"{mod.display_name} -> {target_label}",
            "detail": f"Source archive: {archive.name if archive else 'not tracked'}",
            "archive": archive,
            "enabled": False,
            "reason": "",
        }
        if archive is None or not archive.is_file():
            base["reason"] = "Missing source archive; install manually from Archives."
            return base
        try:
            info = inspect_archive(archive)
        except Exception as exc:
            base["reason"] = f"Could not inspect archive: {exc}"
            return base
        if info.has_variants or mod.selected_variant:
            base["reason"] = "Variant archive; use full compare/install review so the exact variant is explicit."
            return base
        if mod.component_map:
            base["reason"] = "Selected bundle components; use full compare/install review to avoid uploading extra pak files."
            return base
        if target == "hosted":
            profile = self.app._server_tab._selected_remote_profile()
            if profile is None:
                base["reason"] = "No hosted profile selected."
                return base
            plan = plan_remote_deployment(info, profile, selected_variant=None, mod_name=mod.display_name)
            if not plan.valid:
                base["reason"] = "; ".join(plan.warnings) or "Hosted upload plan is not valid."
                return base
            base.update({"enabled": True, "kind": "hosted_upload", "info": info})
            base["detail"] = f"Upload {plan.file_count} file(s) from {archive.name} to hosted ~mods."
            return base

        target_enum = InstallTarget.SERVER if target == "server" else InstallTarget.DEDICATED_SERVER
        plan, error = self.app._mods_tab._prepare_install_target(info, mod.display_name, target_enum, None)
        if plan is None:
            base["reason"] = error or "Install plan is not valid."
            return base
        conflict_report = check_plan_conflicts(plan, self.app.manifest)
        if conflict_report.has_conflicts:
            base["reason"] = "Managed file conflict detected; open full compare/install review first."
            return base
        base.update(
            {
                "enabled": True,
                "kind": "local_install",
                "preset": "local" if target == "server" else "dedicated",
                "info": info,
            }
        )
        base["detail"] = f"Install {archive.name} to {target_label} using existing backup/history flow."
        return base

    def _apply_local_sync_actions(self, actions: list[dict], target: str, dialog, status, apply_btn) -> None:
        success = 0
        failed = 0
        for action in actions:
            try:
                ok = self.app._mods_tab._run_install_preset(
                    action["info"],
                    action["name"],
                    action["preset"],
                    None,
                    quiet=True,
                    confirm_conflicts=False,
                )
                success += 1 if ok else 0
                failed += 0 if ok else 1
            except Exception:
                failed += 1
        status.configure(
            text=f"Applied {success} sync action(s). {failed} failed." if failed else f"Applied {success} sync action(s).",
            text_color="#2d8a4e" if success and not failed else "#e67e22",
        )
        apply_btn.configure(state="normal", text="Apply Selected")
        self._set_server_target_from_dashboard(refresh_inventory=False)
        self.app._server_tab.compare_now()
        self.refresh_view()

    def _apply_hosted_sync_actions(self, actions: list[dict], dialog, status, apply_btn) -> None:
        profile = self.app._server_tab._selected_remote_profile()
        if profile is None:
            status.configure(text="No hosted profile selected.", text_color="#c0392b")
            apply_btn.configure(state="normal", text="Apply Selected")
            return
        status.configure(text="Uploading selected mods to hosted server...", text_color="#95a5a6")

        def _work() -> None:
            success = 0
            failed = 0
            failed_messages: list[str] = []
            for action in actions:
                try:
                    plan = plan_remote_deployment(action["info"], profile, selected_variant=None, mod_name=action["name"])
                    result = self.app.remote_deployer.deploy(plan, profile)
                    if result.failed:
                        failed += 1
                        failed_messages.extend(result.failed[:2])
                    else:
                        success += 1
                        self.app._server_tab._record_hosted_upload(
                            archive_path=action.get("archive"),
                            display_name=action["name"],
                            profile=profile,
                            plan=plan,
                            result=result,
                            notes=f"Dashboard sync uploaded {action['name']} to hosted server {profile.name} ({result.summary})",
                        )
                except Exception as exc:
                    failed += 1
                    failed_messages.append(f"{action['name']}: {exc}")

            def _show() -> None:
                if not status.winfo_exists():
                    return
                text = f"Uploaded {success} hosted sync action(s)."
                if failed:
                    text += f" {failed} failed."
                    if failed_messages:
                        text += " " + "; ".join(failed_messages[:3])
                status.configure(text=text, text_color="#2d8a4e" if success and not failed else "#e67e22")
                if apply_btn.winfo_exists():
                    apply_btn.configure(state="normal", text="Apply Selected")
                self.app._server_tab._refresh_server_inventory()
                self._set_server_target_from_dashboard(refresh_inventory=False)
                self.app._server_tab.compare_now()
                self.refresh_view()

            self.app.dispatch_to_ui(_show)

        threading.Thread(target=_work, daemon=True).start()

    @staticmethod
    def _target_label(target: str) -> str:
        return {
            "server": "Local Server",
            "dedicated_server": "Dedicated Server",
            "hosted": "Hosted Server",
        }.get(target, target.replace("_", " ").title())

    @staticmethod
    def _open_folder(path) -> bool:
        if path and path.exists():
            try:
                os.startfile(str(path))
            except OSError:
                subprocess.Popen(["explorer", str(path)])
            return True
        return False

    def _open_client_mods_folder(self) -> None:
        if not self._open_folder(self.app.paths.client_mods):
            self.app._server_tab._set_result("Client mods folder is not configured.", level="warning")

    def _open_local_server_mods_folder(self) -> None:
        if not self._open_folder(self.app.paths.server_mods):
            self.app._server_tab._set_result("Local server mods folder is not configured.", level="warning")

    def _open_dedicated_server_mods_folder(self) -> None:
        if not self._open_folder(self.app.paths.dedicated_server_mods):
            self.app._server_tab._set_result("Dedicated server mods folder is not configured.", level="warning")

    def apply_ui_preferences(self) -> None:
        self._title.configure(font=self.app.ui_font("title"))
        self._subtitle.configure(font=self.app.ui_font("small"), wraplength=self.app.ui_tokens.detail_wrap)
        for label in self._status_values.values():
            label.configure(font=self.app.ui_font("body"))
        for label in self._setup_values.values():
            label.configure(font=self.app.ui_font("body"), wraplength=self.app.ui_tokens.panel_wrap - 40)
        for label in self._count_values.values():
            label.configure(font=self.app.ui_font("body"))
        for label in self._framework_values.values():
            label.configure(font=self.app.ui_font("body"), wraplength=self.app.ui_tokens.panel_wrap)
        self._framework_note.configure(font=self.app.ui_font("small"), wraplength=self.app.ui_tokens.panel_wrap)
        self._compare_target_menu.configure(font=self.app.ui_font("body"), height=self.app.ui_tokens.compact_button_height)
        self._parity_state.configure(font=self.app.ui_font("row_title"))
        self._parity_summary.configure(font=self.app.ui_font("small"), wraplength=self.app.ui_tokens.panel_wrap)
        self._drift_label.configure(font=self.app.ui_font("small"), wraplength=self.app.ui_tokens.panel_wrap)
        for button in self._action_buttons:
            button.configure(font=self.app.ui_font("body"), height=self.app.ui_tokens.compact_button_height)

    def refresh_view(self) -> None:
        server_tab = self.app._server_tab
        counts = server_tab._dashboard_target_counts()
        source_label = "Hosted Server" if server_tab._source_var.get() == "hosted" else server_tab._active_local_label()
        active_world = server_tab._world_display_name(server_tab._world_config)
        hosted_profile = server_tab._selected_remote_profile()
        hosted_name = hosted_profile.name if hosted_profile is not None else "Not selected"

        client_state = self._status_text(self.app.is_game_running(), configured=True)
        local_state = self._server_status_text("server")
        dedicated_state = self._server_status_text("dedicated_server")
        hosted_state = server_tab._hosted_dashboard_state
        framework_states = self.app.framework_state.all_local_states(self.app.paths)

        self._set_state_label(self._status_values["client"], client_state)
        self._set_state_label(self._status_values["server"], local_state)
        self._set_state_label(self._status_values["dedicated_server"], dedicated_state)
        self._set_state_label(self._status_values["hosted"], hosted_state)
        self._refresh_frameworks(framework_states)

        self._setup_values["source"].configure(text=source_label)
        self._setup_values["world"].configure(text=active_world)
        self._setup_values["profile"].configure(text=hosted_name if server_tab._source_var.get() == "hosted" else "N/A")
        self._setup_values["apply"].configure(text=server_tab._last_apply_text())
        self._setup_values["restart"].configure(text=server_tab._last_restart_text())
        self._setup_values["backup"].configure(text=server_tab._last_backup_text())

        compare_state, compare_summary = server_tab.dashboard_parity_state()
        drift_warnings = getattr(self.app, "manifest_drift_warnings", lambda: [])()
        state_text, state_color = {
            "clean": ("Compare looks clean", "#2d8a4e"),
            "review": ("Review recommended", "#e67e22"),
            "not_run": ("No compare run yet", "#95a5a6"),
        }.get(compare_state, ("Review recommended", "#e67e22"))
        if drift_warnings:
            state_text, state_color = "Review recommended", "#e67e22"
        self._parity_state.configure(text=state_text, text_color=state_color)
        self._parity_summary.configure(text=compare_summary)
        if drift_warnings:
            count = len(drift_warnings)
            self._drift_label.configure(text=f"Drift detected: {count} managed mod issue(s). Open Mods or Activity to review.")
        else:
            self._drift_label.configure(text="")
        can_review_sync = (
            server_tab.last_compare_target() == self._dashboard_target_key()
            and server_tab.last_compare_report() is not None
            and server_tab.last_compare_report().review_needed > 0
        )
        self._review_sync_btn.configure(
            state="normal" if can_review_sync else "disabled",
            fg_color="#e67e22" if can_review_sync else "#555555",
            hover_color="#d35400" if can_review_sync else "#666666",
        )
        for key, value in counts.items():
            self._count_values[key].configure(text=str(value))

    def _server_status_text(self, target: str) -> str:
        configured = bool(self.app.paths.server_root if target == "server" else self.app.paths.dedicated_server_root)
        if not configured:
            return "Not configured"
        running = self.app.is_server_process_running()
        if not running:
            return "Configured"
        if self.app.paths.server_root and not self.app.paths.dedicated_server_root and target == "server":
            return "Running"
        if self.app.paths.dedicated_server_root and not self.app.paths.server_root and target == "dedicated_server":
            return "Running"
        active_target = self.app._server_tab._source_var.get()
        if active_target == target:
            return "Running"
        return "Configured"

    def _refresh_frameworks(self, states: dict) -> None:
        self._set_framework_label(
            self._framework_values["ue4ss"],
            self._ue4ss_text(states),
        )
        self._set_framework_label(
            self._framework_values["rcon"],
            self._rcon_text(states),
        )
        self._set_framework_label(
            self._framework_values["windrose_plus"],
            self._windrose_plus_text(states),
        )

    @staticmethod
    def _framework_target_names(states: dict, attribute: str) -> list[str]:
        labels = {
            "client": "Client",
            "server": "Local",
            "dedicated_server": "Dedicated",
        }
        return [labels[key] for key, state in states.items() if getattr(state, attribute, False)]

    @classmethod
    def _framework_targets_text(cls, states: dict, attribute: str, *, empty: str) -> str:
        targets = cls._framework_target_names(states, attribute)
        return ", ".join(targets) if targets else empty

    @classmethod
    def _ue4ss_text(cls, states: dict) -> str:
        installed = cls._framework_target_names(states, "ue4ss_runtime")
        partial = cls._framework_target_names(states, "ue4ss_partial")
        parts = []
        if installed:
            parts.append(", ".join(installed))
        if partial:
            label = "Review" if installed else "Runtime missing"
            parts.append(f"{label}: {', '.join(partial)}")
        return " | ".join(parts) if parts else "Missing"

    @classmethod
    def _rcon_text(cls, states: dict) -> str:
        client_state = states.get("client")
        client_installed = bool(getattr(client_state, "rcon_mod", False))
        server_states = {key: state for key, state in states.items() if key != "client"}
        installed = cls._framework_target_names(server_states, "rcon_mod")
        needs_password = cls._framework_target_names(server_states, "rcon_missing_password")
        parts = []
        if installed:
            parts.append(", ".join(installed))
        if client_installed:
            parts.append("Wrong target: Client")
        if not parts:
            return "Not installed"
        if needs_password:
            parts.append(f"Password review: {', '.join(needs_password)}")
        return " | ".join(parts)

    @classmethod
    def _windrose_plus_text(cls, states: dict) -> str:
        active = cls._framework_target_names(states, "windrose_plus")
        generated = cls._framework_target_names(states, "windrose_plus_generated_paks")
        wrappers = cls._framework_target_names(states, "windrose_plus_launch_wrapper")
        partial = cls._framework_target_names(states, "windrose_plus_partial")
        files = [
            target
            for target, state in zip(
                ["Client", "Local", "Dedicated"],
                [states.get("client"), states.get("server"), states.get("dedicated_server")],
            )
            if state and state.windrose_plus_package and not state.windrose_plus
        ]
        parts = []
        if active:
            parts.append(f"Active on {', '.join(active)}")
        if generated:
            parts.append(f"Generated PAKs on {', '.join(generated)}")
        if wrappers:
            parts.append(f"Wrapper on {', '.join(wrappers)}")
        if files:
            parts.append(f"Files on {', '.join(files)}")
        if partial:
            parts.append(f"Review {', '.join(partial)}")
        return " | ".join(parts) if parts else "Not installed"

    @staticmethod
    def _set_framework_label(label: ctk.CTkLabel, value: str) -> None:
        normalized = value.lower()
        if "missing" in normalized or "files on" in normalized or "partial" in normalized or "review" in normalized or "wrong target" in normalized:
            color = "#e67e22"
        elif "not installed" in normalized:
            color = "#95a5a6"
        else:
            color = "#2d8a4e"
        label.configure(text=value, text_color=color)

    @staticmethod
    def _status_text(running: bool, *, configured: bool) -> str:
        if not configured:
            return "Not configured"
        return "Running" if running else "Not running"

    @staticmethod
    def _set_state_label(label: ctk.CTkLabel, value: str) -> None:
        normalized = value.lower()
        if "offline" in normalized:
            color = "#c0392b"
        elif "not configured" in normalized or "not running" in normalized:
            color = "#95a5a6"
        elif "running" in normalized or "connected" in normalized:
            color = "#2d8a4e"
        elif "missing" in normalized:
            color = "#e67e22"
        elif normalized == "configured":
            color = "#95a5a6"
        else:
            color = "#e67e22"
        label.configure(text=value, text_color=color)
