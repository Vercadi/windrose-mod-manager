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
        self._build()

    def _build(self) -> None:
        body = ctk.CTkScrollableFrame(self)
        body.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self._title = ctk.CTkLabel(body, text="Dashboard", font=self.app.ui_font("title"))
        self._title.grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))

        self._summary_card = ctk.CTkFrame(body)
        self._summary_card.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        self._summary_card.grid_columnconfigure(0, weight=1)
        self._summary_text = ctk.CTkLabel(
            self._summary_card,
            text="",
            justify="left",
            anchor="w",
            wraplength=self.app.ui_tokens.panel_wrap * 2,
            font=self.app.ui_font("body"),
        )
        self._summary_text.grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        self._status_card = ctk.CTkFrame(body)
        self._status_card.grid(row=2, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        self._status_card.grid_columnconfigure(0, weight=1)
        self._status_title = ctk.CTkLabel(self._status_card, text="Status", font=self.app.ui_font("card_title"))
        self._status_title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self._status_text = ctk.CTkLabel(
            self._status_card,
            text="",
            justify="left",
            anchor="w",
            wraplength=self.app.ui_tokens.panel_wrap,
            font=self.app.ui_font("body"),
        )
        self._status_text.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        self._counts_card = ctk.CTkFrame(body)
        self._counts_card.grid(row=2, column=1, sticky="nsew", padx=(4, 8), pady=(0, 8))
        self._counts_card.grid_columnconfigure(0, weight=1)
        self._counts_title = ctk.CTkLabel(self._counts_card, text="Installed Mods", font=self.app.ui_font("card_title"))
        self._counts_title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self._counts_text = ctk.CTkLabel(
            self._counts_card,
            text="",
            justify="left",
            anchor="w",
            wraplength=self.app.ui_tokens.panel_wrap,
            font=self.app.ui_font("body"),
        )
        self._counts_text.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        self._actions_card = ctk.CTkFrame(body)
        self._actions_card.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        self._actions_card.grid_columnconfigure(0, weight=1)
        self._actions_title = ctk.CTkLabel(self._actions_card, text="Quick Actions", font=self.app.ui_font("card_title"))
        self._actions_title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        buttons_top = ctk.CTkFrame(self._actions_card, fg_color="transparent")
        buttons_top.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        buttons_bottom = ctk.CTkFrame(self._actions_card, fg_color="transparent")
        buttons_bottom.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

        self._launch_game_btn = ctk.CTkButton(
            buttons_top,
            text="Launch Windrose",
            width=132,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#2d8a4e",
            hover_color="#236b3d",
            command=self.app._on_start_game,
        )
        self._launch_game_btn.pack(side="left", padx=(0, 6))
        self._launch_server_btn = ctk.CTkButton(
            buttons_top,
            text="Launch Dedicated Server",
            width=168,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self.app._on_start_server,
        )
        self._launch_server_btn.pack(side="left", padx=6)
        self._open_server_btn = ctk.CTkButton(
            buttons_top,
            text="Open Server Folder",
            width=140,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: self.app._server_tab._open_active_server_folder(),
        )
        self._open_server_btn.pack(side="left", padx=6)
        self._open_settings_btn = ctk.CTkButton(
            buttons_top,
            text="Open Settings Folder",
            width=136,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: self.app._server_tab._open_active_settings_file(),
        )
        self._open_settings_btn.pack(side="left", padx=6)
        self._open_client_mods_btn = ctk.CTkButton(
            buttons_bottom,
            text="Open Client Mods",
            width=136,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._open_client_mods_folder,
        )
        self._open_client_mods_btn.pack(side="left", padx=(0, 6))
        self._open_local_server_mods_btn = ctk.CTkButton(
            buttons_bottom,
            text="Open Local Server Mods",
            width=172,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._open_local_server_mods_folder,
        )
        self._open_local_server_mods_btn.pack(side="left", padx=6)
        self._open_dedicated_server_mods_btn = ctk.CTkButton(
            buttons_bottom,
            text="Open Dedicated Server Mods",
            width=194,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._open_dedicated_server_mods_folder,
        )
        self._open_dedicated_server_mods_btn.pack(side="left", padx=6)
        self._compare_btn = ctk.CTkButton(
            buttons_bottom,
            text="Run Compare",
            width=112,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=self._run_compare,
        )
        self._compare_btn.pack(side="left", padx=6)
        self._backup_btn = ctk.CTkButton(
            buttons_bottom,
            text="Back Up Now",
            width=112,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: self.app._server_tab._on_backup_now(),
        )
        self._backup_btn.pack(side="left", padx=6)

    def _run_compare(self) -> None:
        self.app._tabview.set("Server")
        self.app._server_tab.compare_now()

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
        wrap = self.app.ui_tokens.panel_wrap * 2
        self._title.configure(font=self.app.ui_font("title"))
        self._status_title.configure(font=self.app.ui_font("card_title"))
        self._counts_title.configure(font=self.app.ui_font("card_title"))
        self._actions_title.configure(font=self.app.ui_font("card_title"))
        self._summary_text.configure(font=self.app.ui_font("body"), wraplength=wrap)
        self._status_text.configure(font=self.app.ui_font("body"), wraplength=self.app.ui_tokens.panel_wrap)
        self._counts_text.configure(font=self.app.ui_font("body"), wraplength=self.app.ui_tokens.panel_wrap)
        for button in (
            self._launch_game_btn,
            self._launch_server_btn,
            self._open_server_btn,
            self._open_settings_btn,
            self._open_client_mods_btn,
            self._open_local_server_mods_btn,
            self._open_dedicated_server_mods_btn,
            self._compare_btn,
            self._backup_btn,
        ):
            button.configure(font=self.app.ui_font("body"), height=self.app.ui_tokens.compact_button_height)

    def refresh_view(self) -> None:
        server_tab = self.app._server_tab
        counts = server_tab._dashboard_target_counts()
        source_label = "Hosted Server" if server_tab._source_var.get() == "hosted" else server_tab._active_local_label()
        active_world = server_tab._world_display_name(server_tab._world_config)
        hosted_profile = server_tab._selected_remote_profile()
        hosted_name = hosted_profile.name if hosted_profile is not None else "(not selected)"
        summary_lines = [
            f"Current source: {source_label}",
            f"Active world: {active_world}",
            f"Hosted profile: {hosted_name} | {server_tab._hosted_dashboard_state}",
            f"Last backup: {server_tab._last_backup_text()}",
            f"Last action: {server_tab._last_apply_text()}",
        ]
        self._summary_text.configure(text="\n".join(summary_lines))

        status_lines = [
            f"Windrose client: {'Running' if self.app.is_game_running() else 'Not running'}",
            f"Local Server: {'Configured' if self.app.paths.server_root else 'Not configured'}",
            f"Dedicated Server: {'Running' if self.app.is_server_process_running() else ('Configured' if self.app.paths.dedicated_server_root else 'Not configured')}",
            f"Hosted Server: {server_tab._hosted_dashboard_state}",
        ]
        self._status_text.configure(text="\n".join(status_lines))

        counts_lines = [
            f"Client: {counts['client']}",
            f"Local Server: {counts['server']}",
            f"Dedicated Server: {counts['dedicated_server']}",
            f"Hosted Server: {counts['hosted']}",
        ]
        self._counts_text.configure(text="\n".join(counts_lines))
