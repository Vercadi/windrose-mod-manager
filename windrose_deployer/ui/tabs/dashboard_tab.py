"""Dashboard tab for operational overview."""
from __future__ import annotations

import os
import subprocess

import customtkinter as ctk


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
        self._build()

    def _build(self) -> None:
        body = ctk.CTkScrollableFrame(self)
        body.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self._title = ctk.CTkLabel(body, text="Dashboard", font=self.app.ui_font("title"))
        self._title.grid(row=0, column=0, sticky="w", padx=8, pady=(0, 2))

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
        self._parity_card = self._make_card(body, row=3, column=0, title="Mod Parity")
        self._actions_card = self._make_card(body, row=3, column=1, title="Quick Actions")

        self._build_status_card()
        self._build_current_card()
        self._build_parity_card()
        self._build_actions_card()

    def _make_card(self, body, *, row: int, column: int, title: str):
        card = ctk.CTkFrame(body)
        card.grid(row=row, column=column, sticky="nsew", padx=8 if column == 0 else (4, 8), pady=(0, 8))
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text=title, font=self.app.ui_font("card_title")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(14, 10)
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
            ).grid(row=index, column=0, sticky="w", padx=14, pady=4)
            value = ctk.CTkLabel(self._status_card, text="", anchor="e", font=self.app.ui_font("body"))
            value.grid(row=index, column=1, sticky="e", padx=14, pady=4)
            self._status_values[key] = value

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
            ).grid(row=index, column=0, sticky="w", padx=14, pady=4)
            value = ctk.CTkLabel(
                self._current_card,
                text="",
                justify="left",
                anchor="e",
                font=self.app.ui_font("body"),
                wraplength=self.app.ui_tokens.panel_wrap - 40,
            )
            value.grid(row=index, column=1, sticky="e", padx=14, pady=4)
            self._setup_values[key] = value

    def _build_parity_card(self) -> None:
        self._parity_state = ctk.CTkLabel(
            self._parity_card,
            text="",
            anchor="w",
            font=self.app.ui_font("row_title"),
        )
        self._parity_state.grid(row=1, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 4))

        self._parity_summary = ctk.CTkLabel(
            self._parity_card,
            text="",
            justify="left",
            anchor="w",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
            wraplength=self.app.ui_tokens.panel_wrap,
        )
        self._parity_summary.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))

        labels = [
            ("client", "Client"),
            ("server", "Local Server"),
            ("dedicated_server", "Dedicated Server"),
            ("hosted", "Hosted Server"),
        ]
        for index, (key, label) in enumerate(labels, start=3):
            ctk.CTkLabel(
                self._parity_card,
                text=label,
                font=self.app.ui_font("body"),
                text_color="#aeb6bf",
            ).grid(row=index, column=0, sticky="w", padx=14, pady=4)
            value = ctk.CTkLabel(self._parity_card, text="0", anchor="e", font=self.app.ui_font("body"))
            value.grid(row=index, column=1, sticky="e", padx=14, pady=4)
            self._count_values[key] = value

        self._compare_btn = ctk.CTkButton(
            self._parity_card,
            text="Run Compare",
            width=126,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=self._run_compare,
        )
        self._compare_btn.grid(row=7, column=0, sticky="w", padx=(14, 6), pady=(10, 14))
        self._action_buttons.append(self._compare_btn)
        self._open_compare_btn = ctk.CTkButton(
            self._parity_card,
            text="Open Full Compare",
            width=146,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._open_full_compare,
        )
        self._open_compare_btn.grid(row=7, column=1, sticky="e", padx=(6, 14), pady=(10, 14))
        self._action_buttons.append(self._open_compare_btn)

    def _build_actions_card(self) -> None:
        actions = ctk.CTkFrame(self._actions_card, fg_color="transparent")
        actions.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=14, pady=(0, 14))
        for column in range(2):
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
            actions, row=1, column=0, text="Open Client Mods", command=self._open_client_mods_folder,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=1, column=1, text="Open Local Server Mods", command=self._open_local_server_mods_folder,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=2, column=0, text="Open Dedicated Server Mods", command=self._open_dedicated_server_mods_folder,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=2, column=1, text="Open Server Folder", command=self.app._server_tab._open_active_server_folder,
            fg="#555555", hover="#666666",
        )
        self._add_action_button(
            actions, row=3, column=0, text="Back Up Now", command=self.app._server_tab._on_backup_now,
            fg="#555555", hover="#666666",
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

    def _run_compare(self) -> None:
        self.app._server_tab.compare_now()

    def _open_full_compare(self) -> None:
        self.app._tabview.set("Server")
        self.app._on_tab_changed("Server")

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
        self._parity_state.configure(font=self.app.ui_font("row_title"))
        self._parity_summary.configure(font=self.app.ui_font("small"), wraplength=self.app.ui_tokens.panel_wrap)
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

        self._set_state_label(self._status_values["client"], client_state)
        self._set_state_label(self._status_values["server"], local_state)
        self._set_state_label(self._status_values["dedicated_server"], dedicated_state)
        self._set_state_label(self._status_values["hosted"], hosted_state)

        self._setup_values["source"].configure(text=source_label)
        self._setup_values["world"].configure(text=active_world)
        self._setup_values["profile"].configure(text=hosted_name if server_tab._source_var.get() == "hosted" else "N/A")
        self._setup_values["apply"].configure(text=server_tab._last_apply_text())
        self._setup_values["restart"].configure(text=server_tab._last_restart_text())
        self._setup_values["backup"].configure(text=server_tab._last_backup_text())

        compare_state, compare_summary = server_tab.dashboard_parity_state()
        state_text, state_color = {
            "clean": ("Compare looks clean", "#2d8a4e"),
            "review": ("Review recommended", "#e67e22"),
            "not_run": ("No compare run yet", "#95a5a6"),
        }.get(compare_state, ("Review recommended", "#e67e22"))
        self._parity_state.configure(text=state_text, text_color=state_color)
        self._parity_summary.configure(text=compare_summary)
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

    @staticmethod
    def _status_text(running: bool, *, configured: bool) -> str:
        if not configured:
            return "Not configured"
        return "Running" if running else "Not running"

    @staticmethod
    def _set_state_label(label: ctk.CTkLabel, value: str) -> None:
        normalized = value.lower()
        if "running" in normalized or "connected" in normalized or "configured" == normalized:
            color = "#2d8a4e" if ("running" in normalized or "connected" in normalized) else "#95a5a6"
        elif "offline" in normalized or "not configured" in normalized:
            color = "#c0392b" if "offline" in normalized else "#95a5a6"
        else:
            color = "#e67e22"
        label.configure(text=value, text_color=color)
