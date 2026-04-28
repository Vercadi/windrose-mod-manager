"""Server tab — edit ServerDescription.json and WorldDescription.json."""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...core.archive_inspector import inspect_archive
from ...core.live_mod_inventory import (
    LiveModsFolderSnapshot,
    bundle_live_file_names,
    snapshot_live_mods_folder,
)
from ...core.remote_deployer import plan_remote_deployment, remote_connection_diagnostics
from ...models.deployment_record import DeployedFile, DeploymentRecord
from ...models.mod_install import expand_target_values
from ...models.remote_profile import (
    RemoteProfile,
    SUPPORTED_REMOTE_PROTOCOLS,
    default_port_for_protocol,
    normalize_remote_endpoint,
    normalize_remote_protocol,
)
from ...models.server_config import ServerConfig
from ...models.world_config import (
    BOOL_PARAM_SPEC,
    FLOAT_PARAM_SPEC,
    PRESET_OPTIONS,
    WorldConfig,
)

if TYPE_CHECKING:
    from ..app_window import AppWindow

log = logging.getLogger(__name__)

_CD_DISPLAY = {
    "WDS.Parameter.CombatDifficulty.Easy": "Easy",
    "WDS.Parameter.CombatDifficulty.Normal": "Normal",
    "WDS.Parameter.CombatDifficulty.Hard": "Hard",
}
_CD_FROM_DISPLAY = {v: k for k, v in _CD_DISPLAY.items()}


class ServerTab(ctk.CTkFrame):
    def __init__(self, master, app: AppWindow, *, defer_initial_refresh: bool = False, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._config: Optional[ServerConfig] = None
        self._world_config: Optional[WorldConfig] = None
        self._world_path: Optional[Path | str] = None
        self._remote_profile_labels: dict[str, str] = {}
        self._source_value = "dedicated_server"
        self._hosted_setup_dialog: ctk.CTkToplevel | None = None
        self._hosted_install_dialog: ctk.CTkToplevel | None = None
        self._action_buttons: list[ctk.CTkButton] = []
        self._field_labels: list[ctk.CTkLabel] = []
        self._field_inputs: list[object] = []
        self._status_boxes: list[ctk.CTkTextbox] = []
        self._hosted_dashboard_state = "Not configured"
        self._hosted_framework_summary = "Unknown"
        self._hosted_dashboard_profile_id: str | None = None
        self._last_compare_summary = "No compare run yet"
        self._last_compare_state = "not_run"
        self._last_compare_target = "dedicated_server"
        self._last_compare_report = None

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_scrollable_body()
        self._build_actions()
        self.refresh_remote_profiles()
        self._on_source_changed("dedicated_server", refresh_inventory=not defer_initial_refresh)

    # ================================================================== layout

    def _build_toolbar(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 4))

        ctk.CTkLabel(frame, text="Server", font=self.app.ui_font("page_title")).pack(
            side="left", padx=8
        )

        self._source_row = ctk.CTkFrame(frame, fg_color="transparent")
        self._source_row.pack(side="left", padx=12)

        self._source_var = ctk.StringVar(value="dedicated_server")
        self._source_switch = ctk.CTkSegmentedButton(
            self._source_row,
            values=["Local Server", "Dedicated Server", "Hosted Server"],
            command=self._on_source_segment_changed,
            font=self.app.ui_font("body"),
        )
        self._source_switch.pack(side="left", padx=(0, 8))
        self._source_switch.set("Dedicated Server")

        self._remote_profile_label = ctk.CTkLabel(self._source_row, text="Hosted Profile:")
        self._remote_profile_var = ctk.StringVar(value="(no remote profiles)")
        self._remote_profile_menu = ctk.CTkOptionMenu(
            self._source_row,
            variable=self._remote_profile_var,
            values=["(no remote profiles)"],
            width=220,
            command=self._on_remote_profile_changed,
        )

        self._hosted_setup_btn = ctk.CTkButton(
            frame,
            text="Hosted Setup",
            width=112,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self.open_hosted_setup,
        )
        self._hosted_setup_btn.pack(side="right", padx=4)
        self._action_buttons.append(self._hosted_setup_btn)
        self._test_btn = ctk.CTkButton(
            frame,
            text="Test Connection",
            width=116,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=self._on_test_connection,
        )
        self._test_btn.pack(side="right", padx=4)
        self._action_buttons.append(self._test_btn)
        self._load_btn = ctk.CTkButton(
            frame,
            text="Load Current Settings",
            width=152,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=self._on_load_all,
        )
        self._load_btn.pack(side="right", padx=4)
        self._action_buttons.append(self._load_btn)
        refresh_btn = ctk.CTkButton(
            frame,
            text="Refresh",
            width=84,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self.refresh_view,
        )
        refresh_btn.pack(side="right", padx=4)
        self._action_buttons.append(refresh_btn)

    def _build_scrollable_body(self) -> None:
        self._body = ctk.CTkScrollableFrame(self)
        self._body.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=4)
        self._body.grid_columnconfigure(0, weight=1)

        self._build_server_section(self._body)
        self._build_world_section(self._body)

    def _poll_scroll_hint(self) -> None:
        """Retained for compatibility with older layout wiring."""
        return

    # ---- Server Description section ----

    def _build_server_section(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        ctk.CTkLabel(header, text="Server Description",
                     font=self.app.ui_font("section_title")).pack(side="left")

        editor = ctk.CTkFrame(parent)
        editor.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        editor.grid_columnconfigure(1, weight=1)

        self._fields: dict[str, ctk.CTkEntry | ctk.CTkCheckBox] = {}

        fields_spec = [
            ("ServerName", "Server Name", "entry"),
            ("InviteCode", "Invite Code", "entry"),
            ("IsPasswordProtected", "Password Protected", "checkbox"),
            ("Password", "Password", "entry"),
            ("MaxPlayerCount", "Max Players", "entry"),
            ("WorldIslandId", "World Island ID", "entry_readonly"),
            ("P2pProxyAddress", "P2P Proxy Address", "entry"),
            ("DeploymentId", "Deployment ID", "entry_readonly"),
            ("PersistentServerId", "Persistent Server ID", "entry_readonly"),
        ]

        for i, (key, label, ftype) in enumerate(fields_spec):
            field_label = ctk.CTkLabel(editor, text=label + ":", anchor="w", font=self.app.ui_font("body"))
            field_label.grid(row=i, column=0, sticky="w", padx=(8, 4), pady=5)
            self._field_labels.append(field_label)

            if ftype == "checkbox":
                var = tk.BooleanVar()
                widget = ctk.CTkCheckBox(editor, text="", variable=var, font=self.app.ui_font("body"))
                widget.grid(row=i, column=1, sticky="w", padx=4, pady=5)
                widget._variable = var
            else:
                var = ctk.StringVar()
                state = "readonly" if ftype == "entry_readonly" else "normal"
                widget = ctk.CTkEntry(editor, textvariable=var, state=state, font=self.app.ui_font("body"))
                widget.grid(row=i, column=1, sticky="ew", padx=(4, 8), pady=5)
                widget._variable = var

            self._fields[key] = widget
            self._field_inputs.append(widget)

        save_row = len(fields_spec)
        self._server_save_btn = ctk.CTkButton(
            editor, text="Apply Server Settings", width=170,
            height=self.app.ui_tokens.button_height,
            font=self.app.ui_font("body"),
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_save_server,
        )
        self._server_save_btn.grid(row=save_row, column=1, sticky="w", padx=4, pady=(8, 4))
        self._action_buttons.append(self._server_save_btn)
        self._server_hint_label = ctk.CTkLabel(
            editor,
            text="World settings continue below this section.",
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._server_hint_label.grid(row=save_row + 1, column=1, sticky="w", padx=4, pady=(0, 6))

    # ---- World Description section ----

    def _build_world_section(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=2, column=0, sticky="ew", pady=(8, 2))
        ctk.CTkLabel(header, text="World Settings",
                     font=self.app.ui_font("section_title")).pack(side="left")
        self._world_info_label = ctk.CTkLabel(header, text="(not loaded)", text_color="#95a5a6", font=self.app.ui_font("small"))
        self._world_info_label.pack(side="left", padx=8)

        editor = ctk.CTkFrame(parent)
        editor.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        editor.grid_columnconfigure(1, weight=1)

        self._world_fields: dict[str, any] = {}
        row = 0

        # World Name
        world_name_label = ctk.CTkLabel(editor, text="World Name:", anchor="w", font=self.app.ui_font("body"))
        world_name_label.grid(row=row, column=0, sticky="w", padx=(8, 4), pady=5)
        self._field_labels.append(world_name_label)
        var = ctk.StringVar()
        w = ctk.CTkEntry(editor, textvariable=var, font=self.app.ui_font("body"))
        w.grid(row=row, column=1, sticky="ew", padx=(4, 8), pady=5)
        w._variable = var
        self._world_fields["WorldName"] = w
        self._field_inputs.append(w)
        row += 1

        # Preset
        preset_label = ctk.CTkLabel(editor, text="Preset:", anchor="w", font=self.app.ui_font("body"))
        preset_label.grid(row=row, column=0, sticky="w", padx=(8, 4), pady=5)
        self._field_labels.append(preset_label)
        self._preset_var = ctk.StringVar(value="Medium")
        self._preset_menu = ctk.CTkOptionMenu(
            editor,
            variable=self._preset_var,
            values=PRESET_OPTIONS,
            width=140,
            font=self.app.ui_font("body"),
            command=self._on_preset_change,
        )
        self._preset_menu.grid(row=row, column=1, sticky="w", padx=4, pady=5)
        row += 1

        # Combat Difficulty
        combat_label = ctk.CTkLabel(editor, text="Combat Difficulty:", anchor="w", font=self.app.ui_font("body"))
        combat_label.grid(row=row, column=0, sticky="w", padx=(8, 4), pady=5)
        self._field_labels.append(combat_label)
        self._combat_diff_var = ctk.StringVar(value="Normal")
        self._combat_menu = ctk.CTkOptionMenu(
            editor,
            variable=self._combat_diff_var,
            values=list(_CD_DISPLAY.values()),
            width=140,
            font=self.app.ui_font("body"),
        )
        self._combat_menu.grid(row=row, column=1, sticky="w", padx=4, pady=5)
        row += 1

        # Separator
        sep = ctk.CTkFrame(editor, height=2, fg_color="#444444")
        sep.grid(row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        row += 1

        # Bool params
        for tag_key, (display_name, default) in BOOL_PARAM_SPEC.items():
            bool_label = ctk.CTkLabel(editor, text=display_name + ":", anchor="w", font=self.app.ui_font("body"))
            bool_label.grid(row=row, column=0, sticky="w", padx=(8, 4), pady=5)
            self._field_labels.append(bool_label)
            var = tk.BooleanVar(value=default)
            cb = ctk.CTkCheckBox(editor, text="", variable=var, font=self.app.ui_font("body"))
            cb.grid(row=row, column=1, sticky="w", padx=4, pady=5)
            cb._variable = var
            self._world_fields[f"bool_{tag_key}"] = cb
            self._field_inputs.append(cb)
            row += 1

        # Another separator
        sep2 = ctk.CTkFrame(editor, height=2, fg_color="#444444")
        sep2.grid(row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        row += 1

        # Float params with sliders
        for tag_key, (display_name, default, lo, hi) in FLOAT_PARAM_SPEC.items():
            float_label = ctk.CTkLabel(editor, text=display_name + ":", anchor="w", font=self.app.ui_font("body"))
            float_label.grid(row=row, column=0, sticky="w", padx=(8, 4), pady=5)
            self._field_labels.append(float_label)

            slider_frame = ctk.CTkFrame(editor, fg_color="transparent")
            slider_frame.grid(row=row, column=1, sticky="ew", padx=(4, 8), pady=5)
            slider_frame.grid_columnconfigure(0, weight=1)

            value_var = ctk.StringVar(value=f"{default:.2f}")
            value_label = ctk.CTkLabel(slider_frame, textvariable=value_var, width=50, font=self.app.ui_font("small"))
            value_label.grid(row=0, column=1, padx=(4, 0))

            slider = ctk.CTkSlider(
                slider_frame,
                from_=lo, to=hi,
                number_of_steps=int((hi - lo) / 0.05),
                command=lambda val, vv=value_var: vv.set(f"{val:.2f}"),
            )
            slider.set(default)
            slider.grid(row=0, column=0, sticky="ew")

            range_label = ctk.CTkLabel(slider_frame, text=f"[{lo} – {hi}]",
                                       text_color="#95a5a6", font=ctk.CTkFont(size=10))
            range_label.grid(row=0, column=2, padx=(4, 0))

            self._world_fields[f"float_{tag_key}"] = (slider, value_var)
            self._field_inputs.append(slider)
            row += 1

        # Save world button
        self._world_save_btn = ctk.CTkButton(
            editor, text="Apply World Settings", width=170,
            height=self.app.ui_tokens.button_height,
            font=self.app.ui_font("body"),
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_save_world,
        )
        self._world_save_btn.grid(row=row, column=1, sticky="w", padx=4, pady=(8, 4))
        self._action_buttons.append(self._world_save_btn)

    # ---- Actions bar ----

    def _build_actions(self) -> None:
        frame = ctk.CTkScrollableFrame(self)
        frame.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=4)
        frame.grid_columnconfigure(0, weight=1)

        dashboard_card = ctk.CTkFrame(frame)
        dashboard_card.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        dashboard_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(dashboard_card, text="Operations Overview", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self._dashboard_summary_label = ctk.CTkLabel(
            dashboard_card,
            text="",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#c1c7cd",
            font=self.app.ui_font("body"),
        )
        self._dashboard_summary_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        self._dashboard_counts_label = ctk.CTkLabel(
            dashboard_card,
            text="",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._dashboard_counts_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))
        dashboard_actions = ctk.CTkFrame(dashboard_card, fg_color="transparent")
        dashboard_actions.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        self._dashboard_backup_btn = ctk.CTkButton(
            dashboard_actions,
            text="Back Up Now",
            width=108,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._on_backup_now,
        )
        self._dashboard_backup_btn.pack(side="left", padx=(0, 6))
        self._dashboard_open_folder_btn = ctk.CTkButton(
            dashboard_actions,
            text="Open Server Folder",
            width=138,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._open_active_server_folder,
        )
        self._dashboard_open_folder_btn.pack(side="left", padx=6)
        self._dashboard_open_settings_btn = ctk.CTkButton(
            dashboard_actions,
            text="Open Settings File",
            width=136,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._open_active_settings_file,
        )
        self._dashboard_open_settings_btn.pack(side="left", padx=6)
        self._dashboard_compare_btn = ctk.CTkButton(
            dashboard_actions,
            text="Run Compare",
            width=110,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=self.compare_now,
        )
        self._dashboard_compare_btn.pack(side="left", padx=6)
        self._dashboard_launch_game_btn = ctk.CTkButton(
            dashboard_actions,
            text="Launch Windrose",
            width=118,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#2d8a4e",
            hover_color="#236b3d",
            command=self.app._on_start_game,
        )
        self._dashboard_launch_game_btn.pack(side="left", padx=6)
        self._dashboard_launch_server_btn = ctk.CTkButton(
            dashboard_actions,
            text="Launch Dedicated Server",
            width=156,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self.app._on_start_server,
        )
        self._dashboard_launch_server_btn.pack(side="left", padx=6)
        self._action_buttons.extend(
            [
                self._dashboard_backup_btn,
                self._dashboard_open_folder_btn,
                self._dashboard_open_settings_btn,
                self._dashboard_compare_btn,
                self._dashboard_launch_game_btn,
                self._dashboard_launch_server_btn,
            ]
        )
        dashboard_card.grid_remove()

        source_card = ctk.CTkFrame(frame)
        source_card.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        source_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(source_card, text="Server Source", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self._source_summary_label = ctk.CTkLabel(
            source_card,
            text="",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#c1c7cd",
            font=self.app.ui_font("body"),
        )
        self._source_summary_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        self._status_label = ctk.CTkLabel(
            source_card,
            text="",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            font=self.app.ui_font("small"),
        )
        self._status_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        inventory_card = ctk.CTkFrame(frame)
        inventory_card.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        inventory_card.grid_columnconfigure(0, weight=1)
        self._inventory_title_label = ctk.CTkLabel(
            inventory_card, text="Server Mods", font=self.app.ui_font("card_title")
        )
        self._inventory_title_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self._inventory_box = ctk.CTkTextbox(inventory_card, height=112, font=self.app.ui_font("mono"))
        self._inventory_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        self._inventory_box.configure(state="disabled")
        self._inventory_btn = ctk.CTkButton(
            inventory_card,
            text="Refresh Server Mods",
            width=148,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self._refresh_server_inventory,
        )
        self._inventory_btn.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))
        self._action_buttons.append(self._inventory_btn)
        self._status_boxes.append(self._inventory_box)

        sync_card = ctk.CTkFrame(frame)
        sync_card.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        sync_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sync_card, text="Sync Review", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self._sync_hint_label = ctk.CTkLabel(
            sync_card,
            text="Run compare to review parity. Use the Server Mods card for the current installed list.",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._sync_hint_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        self._sync_box = ctk.CTkTextbox(sync_card, height=126, font=self.app.ui_font("mono"))
        self._sync_box.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))
        self._sync_box.configure(state="disabled")
        self._compare_btn = ctk.CTkButton(
            sync_card,
            text="Run Compare",
            width=204,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=self.compare_now,
        )
        self._compare_btn.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 10))
        self._action_buttons.append(self._compare_btn)
        self._status_boxes.append(self._sync_box)

        apply_card = ctk.CTkFrame(frame)
        apply_card.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        apply_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(apply_card, text="Apply Summary", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self._apply_box = ctk.CTkTextbox(apply_card, height=108, font=self.app.ui_font("mono"))
        self._apply_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        self._apply_box.configure(state="disabled")
        self._confirm_var = tk.BooleanVar(value=False)
        self._confirm_check = ctk.CTkCheckBox(
            apply_card,
            text="Skip extra confirmation popup for this apply",
            variable=self._confirm_var,
            font=self.app.ui_font("body"),
        )
        self._confirm_check.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 6))
        self._confirm_hint = ctk.CTkLabel(
            apply_card,
            text="Leave this unchecked if you want a final confirmation popup before writing changes.",
            justify="left",
            wraplength=self.app.ui_tokens.panel_wrap,
            text_color="#95a5a6",
            font=self.app.ui_font("small"),
        )
        self._confirm_hint.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 6))
        action_row = ctk.CTkFrame(apply_card, fg_color="transparent")
        action_row.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 8))
        self._apply_btn = ctk.CTkButton(
            action_row,
            text="Apply Changes",
            width=122,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#2d8a4e",
            hover_color="#236b3d",
            command=self._on_apply_changes,
        )
        self._apply_btn.pack(side="left", padx=(0, 6))
        self._apply_restart_btn = ctk.CTkButton(
            action_row,
            text="Apply and Restart",
            width=132,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#e67e22",
            hover_color="#ca6b18",
            command=self._on_apply_and_restart,
        )
        self._apply_restart_btn.pack(side="left", padx=6)
        self._action_buttons.extend([self._apply_btn, self._apply_restart_btn])
        self._status_boxes.append(self._apply_box)

        recovery_card = ctk.CTkFrame(frame)
        recovery_card.grid(row=5, column=0, sticky="ew", pady=(0, 6))
        recovery_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(recovery_card, text="Activity Shortcut", font=self.app.ui_font("card_title")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self._restore_server_btn = ctk.CTkButton(
            recovery_card,
            text="Restore Previous Server Settings",
            width=220,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=self._on_restore_server,
        )
        self._restore_server_btn.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 5))
        self._restore_world_btn = ctk.CTkButton(
            recovery_card,
            text="Restore Previous World Settings",
            width=220,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            command=self._on_restore_world,
        )
        self._restore_world_btn.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 5))
        self._open_recovery_btn = ctk.CTkButton(
            recovery_card,
            text="Open Activity & Backups",
            width=180,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self.app.open_recovery_center,
        )
        self._open_recovery_btn.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 10))
        self._action_buttons.extend([self._restore_server_btn, self._restore_world_btn, self._open_recovery_btn])

    def refresh_remote_profiles(self) -> None:
        previous_profile_id = self._hosted_dashboard_profile_id
        profiles = self.app.remote_profiles.list_profiles()
        self._remote_profile_labels = {}
        values = ["(no remote profiles)"]
        for profile in profiles:
            label = profile.name
            if profile.host:
                label = f"{profile.name} [{profile.host}]"
            self._remote_profile_labels[label] = profile.profile_id
            values.append(label)
        self._remote_profile_menu.configure(values=values)
        if profiles:
            if self._remote_profile_var.get() not in self._remote_profile_labels:
                self._remote_profile_var.set(values[1])
        elif self._remote_profile_var.get() not in values:
            self._remote_profile_var.set(values[0])
        selected = self._selected_remote_profile()
        if selected is None:
            self._hosted_dashboard_state = "Not configured"
            self._hosted_framework_summary = "Unknown"
            self._hosted_dashboard_profile_id = None
        elif selected.profile_id != previous_profile_id or self._hosted_dashboard_state == "Checking connection...":
            self._hosted_dashboard_state = "Configured"
            self._hosted_framework_summary = "Unknown"
            self._hosted_dashboard_profile_id = selected.profile_id
        self._update_source_summary()

    def remote_profile_options(self) -> list[str]:
        return list(self._remote_profile_menu.cget("values"))

    def selected_remote_profile_label(self) -> str:
        return self._remote_profile_var.get()

    def select_remote_profile_label(self, label: str, *, refresh_inventory: bool = False) -> None:
        if label not in set(self.remote_profile_options()):
            return
        self._remote_profile_var.set(label)
        self._on_remote_profile_changed(label, refresh_inventory=refresh_inventory)

    def _on_remote_profile_changed(self, _value: str, *, refresh_inventory: bool = False) -> None:
        profile = self._selected_remote_profile()
        if profile is None:
            self._hosted_dashboard_state = "Not configured"
            self._hosted_framework_summary = "Unknown"
            self._hosted_dashboard_profile_id = None
        else:
            self._hosted_dashboard_state = "Configured"
            self._hosted_framework_summary = "Unknown"
            self._hosted_dashboard_profile_id = profile.profile_id
        self._update_source_summary()
        self._update_sync_placeholder(force=True)
        if self._source_var.get() == "hosted":
            self._status_label.configure(
                text="Hosted profile selected. Use Test Connection or Load Current Settings when ready.",
                text_color="#95a5a6",
            )
            self._inventory_title_label.configure(text="Hosted Server Mods")
            if refresh_inventory:
                self._refresh_server_inventory()
            elif profile is None:
                self._set_status_box(self._inventory_box, "Choose a hosted profile first.")
            else:
                self._set_status_box(self._inventory_box, "Select Refresh Server Mods to load the hosted ~mods inventory.")
        self._refresh_dashboard()
        if "_dashboard_tab" in self.app.__dict__:
            self.app._dashboard_tab.refresh_view()

    def _on_source_changed(self, value: str, *, refresh_inventory: bool = True) -> None:
        self._source_value = value
        self._source_var.set(value)
        is_hosted = value == "hosted"
        if is_hosted:
            if not self._remote_profile_label.winfo_manager():
                self._remote_profile_label.pack(side="left", padx=(0, 4))
            if not self._remote_profile_menu.winfo_manager():
                self._remote_profile_menu.pack(side="left")
            if not self._test_btn.winfo_manager():
                self._test_btn.pack(side="right", padx=4, before=self._hosted_setup_btn)
            self._test_btn.configure(state="normal")
            self._confirm_var.set(False)
            self._confirm_check.configure(state="disabled")
            self._confirm_hint.configure(
                text="Hosted applies follow the current confirmation behavior and always create recovery backups before writing changes.",
            )
            self._status_label.configure(
                text="Hosted Server source selected. Load current settings after choosing a hosted profile.",
                text_color="#95a5a6",
            )
        else:
            if self._remote_profile_label.winfo_manager():
                self._remote_profile_label.pack_forget()
            if self._remote_profile_menu.winfo_manager():
                self._remote_profile_menu.pack_forget()
            if self._test_btn.winfo_manager():
                self._test_btn.pack_forget()
            self._confirm_check.configure(state="normal")
            self._confirm_hint.configure(
                text="Leave this unchecked if you want a final apply popup before writing changes. Disable All Confirmations in Settings overrides this.",
            )
            self._status_label.configure(
                text=f"{self._active_local_label()} source selected. Load current settings to review server and world config.",
                text_color="#95a5a6",
            )

        self._config = None
        self._world_config = None
        self._world_path = None
        self._clear_server_fields()
        self._clear_world_fields()
        self._update_source_summary()
        self._update_apply_summary()
        self._update_sync_placeholder(force=True)
        if is_hosted:
            self._inventory_title_label.configure(text="Hosted Server Mods")
            if self._selected_remote_profile() is None:
                self._set_status_box(self._inventory_box, "Choose a hosted profile first.")
            else:
                self._set_status_box(self._inventory_box, "Select Refresh Server Mods to load the hosted ~mods inventory.")
        elif refresh_inventory:
            self._refresh_server_inventory()
        self._refresh_dashboard()

    def _on_source_segment_changed(self, value: str) -> None:
        source = value.strip().lower().replace(" ", "_")
        mapped = {
            "local_server": "server",
            "dedicated_server": "dedicated_server",
            "hosted_server": "hosted",
        }.get(source, source)
        self._on_source_changed(mapped)

    def set_source_for_compare(self, source: str, *, refresh_inventory: bool = False) -> None:
        """Select the server source used by Dashboard/Server compare actions."""
        normalized = {
            "local_server": "server",
            "server": "server",
            "dedicated": "dedicated_server",
            "dedicated_server": "dedicated_server",
            "hosted_server": "hosted",
            "hosted": "hosted",
        }.get(source, source)
        label = {
            "server": "Local Server",
            "dedicated_server": "Dedicated Server",
            "hosted": "Hosted Server",
        }.get(normalized)
        if label:
            self._source_switch.set(label)
        if self._source_var.get() == normalized:
            if refresh_inventory:
                self._refresh_server_inventory()
            return
        self._on_source_changed(normalized, refresh_inventory=refresh_inventory)

    def refresh_view(self) -> None:
        self.refresh_remote_profiles()
        self._update_source_summary()
        self._update_apply_summary()
        self._update_sync_placeholder()
        if self._source_var.get() == "hosted":
            self._inventory_title_label.configure(text="Hosted Server Mods")
            if self._selected_remote_profile() is None:
                self._set_status_box(self._inventory_box, "Choose a hosted profile first.")
            else:
                self._set_status_box(self._inventory_box, "Select Refresh Server Mods to load the hosted ~mods inventory.")
        else:
            self._refresh_server_inventory()
        self._refresh_dashboard()

    def _active_local_target(self) -> str:
        return "server" if self._source_var.get() == "server" else "dedicated_server"

    def _active_local_label(self) -> str:
        return "Local Server" if self._source_var.get() == "server" else "Dedicated Server"

    def _active_local_root(self) -> Optional[Path]:
        if self._source_var.get() == "server":
            return self.app.paths.server_root
        return self.app.paths.dedicated_server_root

    def _active_local_server_config_path(self) -> Optional[Path]:
        if self._source_var.get() == "server":
            return self.app.paths.bundled_server_description_json
        return self.app.paths.dedicated_server_description_json

    def _active_local_save_root(self) -> Optional[Path]:
        if self._source_var.get() == "server":
            return self.app.paths.bundled_server_save_root
        return self.app.paths.dedicated_server_save_root

    def _active_local_world_hint(self) -> str:
        if self._source_var.get() == "server":
            return "Local Server Folder"
        return "Dedicated Server World Saves Folder"

    def _dashboard_target_counts(self) -> dict[str, int]:
        counts = {"client": 0, "server": 0, "dedicated_server": 0, "hosted": 0}
        for mod in self.app.manifest.list_mods():
            targets = self._effective_targets(mod)
            for key in counts:
                if key in targets:
                    counts[key] += 1
        return counts

    def _last_backup_text(self) -> str:
        backups = sorted(self.app.backup.list_backups(), key=lambda item: item.timestamp, reverse=True)
        if not backups:
            return "No backups yet"
        latest = backups[0]
        return f"{latest.category.replace('_', ' ').title()} @ {latest.timestamp[:19].replace('T', ' ')}"

    def _last_apply_text(self) -> str:
        actions = {
            "save_server_config",
            "save_world_config",
            "save_remote_server_config",
            "save_remote_world_config",
        }
        for record in reversed(self.app.manifest.list_history()):
            if record.action in actions:
                label = record.action.replace("_", " ")
                return f"{label.title()} @ {record.timestamp[:19].replace('T', ' ')}"
        return "No recent apply actions"

    def _last_restart_text(self) -> str:
        actions = {
            "hosted_restart",
            "launch_server",
        }
        for record in reversed(self.app.manifest.list_history()):
            if record.action in actions:
                label = record.action.replace("_", " ")
                return f"{label.title()} @ {record.timestamp[:19].replace('T', ' ')}"
        return "No restart or launch yet"

    def dashboard_parity_state(self) -> tuple[str, str]:
        return self._last_compare_state, self._last_compare_summary

    def last_compare_target(self) -> str:
        return self._last_compare_target

    def last_compare_report(self):
        return self._last_compare_report

    def _compare_target_label(self, target: str | None = None) -> str:
        source = target or self._source_var.get()
        if source == "hosted":
            return "Hosted Server"
        if source == "server":
            return "Local Server"
        return "Dedicated Server"

    def _remember_compare_report(self, report, target: str | None = None) -> None:
        target_key = target or self._source_var.get()
        self._last_compare_target = target_key
        self._last_compare_report = report
        self._last_compare_summary = f"Client vs {self._compare_target_label(target_key)}: {report.summary}"
        self._last_compare_state = "clean" if report.review_needed == 0 and report.items else ("review" if report.review_needed else "not_run")
        if "_dashboard_tab" in self.app.__dict__:
            self.app._dashboard_tab.refresh_view()

    def _remember_compare_error(self, message: str, target: str | None = None) -> None:
        self._last_compare_target = target or self._source_var.get()
        self._last_compare_report = None
        self._last_compare_state = "review"
        self._last_compare_summary = f"Client vs {self._compare_target_label(self._last_compare_target)}: {message}"
        if "_dashboard_tab" in self.app.__dict__:
            self.app._dashboard_tab.refresh_view()

    @staticmethod
    def _world_display_name(config: WorldConfig | None) -> str:
        if config is None:
            return "(not loaded)"
        name = (config.world_name or "").strip()
        return name or "(unnamed world)"

    def _refresh_dashboard(self) -> None:
        counts = self._dashboard_target_counts()
        active_world = self._world_display_name(self._world_config)
        source_label = "Hosted Server" if self._source_var.get() == "hosted" else self._active_local_label()
        client_state = "Running" if self.app.is_game_running() else "Not running"
        if self._source_var.get() == "hosted":
            hosted_state = self._hosted_dashboard_state
            server_line = f"Hosted Server: {hosted_state}"
        elif self._source_var.get() == "server":
            hosted_state = self._hosted_dashboard_state
            server_line = f"Local Server: {'Configured' if self.app.paths.server_root else 'Not configured'}"
        else:
            hosted_state = self._hosted_dashboard_state
            dedicated_state = (
                "Running"
                if self.app.is_server_process_running()
                else ("Configured" if self.app.paths.dedicated_server_root else "Not configured")
            )
            server_line = f"Dedicated Server: {dedicated_state}"
        summary_lines = [
            f"Current source: {source_label}",
            f"Windrose client: {client_state}",
            server_line,
            f"Hosted profile: {hosted_state}",
            f"Frameworks: {self._active_framework_summary()}",
            f"Active world: {active_world}",
            f"Last backup: {self._last_backup_text()}",
            f"Last action: {self._last_apply_text()}",
        ]
        self._dashboard_summary_label.configure(text="\n".join(summary_lines))
        self._dashboard_counts_label.configure(
            text=(
                f"Mod counts | Client: {counts['client']} | "
                f"Local Server: {counts['server']} | "
                f"Dedicated Server: {counts['dedicated_server']} | "
                f"Hosted Server: {counts['hosted']}"
            )
        )

    def _refresh_hosted_dashboard_state(self) -> None:
        profile = self._selected_remote_profile()
        if profile is None:
            self._hosted_dashboard_state = "Not configured"
            self._hosted_framework_summary = "Unknown"
            self._hosted_dashboard_profile_id = None
            self._refresh_dashboard()
            return
        self._hosted_dashboard_state = "Configured"
        self._hosted_framework_summary = "Unknown"
        self._hosted_dashboard_profile_id = profile.profile_id
        self._refresh_dashboard()

    def _active_framework_summary(self) -> str:
        if self._source_var.get() == "hosted":
            return self._hosted_framework_summary
        state = self.app.framework_state.local_state(self._active_local_root())
        return state.summary

    def _open_active_server_folder(self) -> None:
        root = self._active_local_root()
        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                self._set_result("Choose a hosted profile first.", level="info")
            else:
                self._set_result("Hosted server folders are managed through the hosted connection flow.", level="info")
            return
        if root is None or not root.exists():
            self._set_result("Server folder is not configured.", level="warning")
            return
        try:
            os.startfile(str(root))
        except OSError:
            subprocess.Popen(["explorer", str(root)])

    def _open_active_settings_file(self) -> None:
        if self._source_var.get() == "hosted":
            self._set_result("Hosted settings are edited through the current server forms.", level="info")
            return
        config_path = self._active_local_server_config_path()
        if config_path is None or not config_path.exists():
            self._set_result("Server settings file was not found.", level="warning")
            return
        try:
            os.startfile(str(config_path.parent))
        except OSError:
            subprocess.Popen(["explorer", str(config_path.parent)])

    def _on_backup_now(self) -> None:
        if self._source_var.get() == "hosted":
            self._set_result("Manual backup now is currently supported for local and dedicated sources only.", level="info")
            return
        backed_up = 0
        config_path = self._active_local_server_config_path()
        if config_path and config_path.exists():
            self.app.backup.backup_file(
                config_path,
                category="server_config",
                description=f"Manual backup of {config_path.name}",
            )
            backed_up += 1
        if isinstance(self._world_path, Path) and self._world_path.exists():
            self.app.backup.backup_file(
                self._world_path,
                category="world_config",
                description=f"Manual backup of {self._world_path.name}",
            )
            backed_up += 1
        if not backed_up:
            self._set_result("Load server/world settings first so there is something to back up.", level="info")
            return
        self.app.manifest.add_record(
            DeploymentRecord(
                mod_id="app:manual_backup",
                action="manual_backup",
                target=self._active_local_target(),
                display_name=self._active_local_label(),
                notes=f"Manual backup created for {self._active_local_label()}",
            )
        )
        self.app.refresh_backups_tab()
        self._refresh_dashboard()
        self._set_result(f"Created {backed_up} backup item(s).", level="success")

    def _update_source_summary(self) -> None:
        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                text = "Mode: Hosted Server\nProfile: (not selected)\nProtocol: (not set)\nServer Folder: (not set)"
            else:
                protocol = normalize_remote_protocol(profile.protocol).upper()
                text = (
                    f"Mode: Hosted Server\n"
                    f"Profile: {profile.name}\n"
                    f"Protocol: {protocol}\n"
                    f"Host: {profile.host}:{profile.port}\n"
                    f"Server Folder: {profile.remote_root_dir or '(not set)'}"
                )
        else:
            label = self._active_local_label()
            text = (
                f"Mode: {label}\n"
                f"{label}: {self._active_local_root() or '(not set)'}\n"
                f"Server Settings: {self._active_local_server_config_path() or '(not detected)'}\n"
                f"World Saves: {self._active_local_save_root() or '(not set)'}"
            )
        self._source_summary_label.configure(text=text)
        self._refresh_dashboard()

    def _update_apply_summary(self) -> None:
        lines = [
            f"Current source: {'Hosted Server' if self._source_var.get() == 'hosted' else self._active_local_label()}",
            "Safe apply: backup copies are created before config writes.",
            "Apply Changes saves the currently loaded editor state.",
            "Apply and Restart saves first, then runs the active restart step.",
            "If the confirmation checkbox stays off, the current confirmation behavior decides whether a final apply popup appears.",
        ]
        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile and profile.supports_remote_execute() and profile.restart_command:
                lines.append("Restart: hosted command is configured.")
            elif profile and not profile.supports_remote_execute():
                lines.append("Restart: unavailable for FTP profiles. FTP supports file access only.")
            else:
                lines.append("Restart: hosted command is not configured.")
        else:
            lines.append(f"Restart: launches the configured {self._active_local_label().lower()} executable.")
        if self._config:
            lines.append(f"Loaded server: {self._config.server_name or '(unnamed)'}")
        if self._world_config:
            lines.append(f"Loaded world: {self._world_config.world_name}")
        self._set_status_box(self._apply_box, "\n".join(lines))

    def _update_sync_placeholder(self, *, force: bool = False) -> None:
        if self._source_var.get() == "hosted":
            self._compare_btn.configure(text="Run Client / Hosted Compare")
            text = (
                "Run compare to review parity between client installs and the hosted server. "
                "Use Hosted Server Mods for the current remote mods-folder contents."
            )
        else:
            self._compare_btn.configure(text=f"Run Client / {self._active_local_label()} Compare")
            label = self._active_local_label().lower()
            text = (
                f"Run compare to review parity between managed client installs and the {label} target. "
                f"Use {self._active_local_label()} Mods for the current local install list."
            )
        self._sync_hint_label.configure(text=text)
        if force or not self._sync_box.get("1.0", "end").strip():
            self._set_status_box(self._sync_box, text)

    def _refresh_server_inventory(self) -> None:
        if self._source_var.get() == "hosted":
            self._inventory_title_label.configure(text="Hosted Server Mods")
            profile = self._selected_remote_profile()
            if profile is None:
                self._set_status_box(self._inventory_box, "Choose a hosted profile first.")
                return
            self._inventory_btn.configure(state="disabled", text="Refreshing...")
            self._set_status_box(self._inventory_box, "Loading hosted mods folder...")

            def _work() -> None:
                try:
                    remote_files = self.app.remote_deployer.list_remote_files(profile)
                    text = self._hosted_server_inventory_text(remote_files)
                    framework_state = self.app.framework_state.remote_state(profile)
                    framework_text = framework_state.summary if framework_state.checked else f"Unknown ({framework_state.warning})"
                    text = f"{text}\n\nFrameworks:\n  {framework_text}"
                    state = "Connected"
                except Exception as exc:
                    text = f"Could not load hosted mod inventory:\n{exc}"
                    framework_text = "Unknown"
                    state = "Offline"

                def _show() -> None:
                    if not self.winfo_exists():
                        return
                    self._inventory_btn.configure(state="normal", text="Refresh Server Mods")
                    self._set_status_box(self._inventory_box, text)
                    self._hosted_dashboard_state = state
                    self._hosted_framework_summary = framework_text
                    self._hosted_dashboard_profile_id = profile.profile_id
                    self._refresh_dashboard()

                self.app.dispatch_to_ui(_show)

            threading.Thread(target=_work, daemon=True).start()
            return

        label = self._active_local_label()
        self._inventory_title_label.configure(text=f"{label} Mods")
        self._inventory_btn.configure(state="normal", text="Refresh Server Mods")
        server_mods = [
            mod for mod in self.app.manifest.list_mods()
            if self._active_local_target() in self._effective_targets(mod)
        ]
        snapshot = snapshot_live_mods_folder(
            self._active_local_mods_dir(),
            server_mods,
            target=self._active_local_target(),
        )
        text = self._local_server_inventory_text(server_mods, label, snapshot)
        text = f"{text}\n\nFrameworks:\n  {self.app.framework_state.local_state(self._active_local_root()).summary}"
        self._set_status_box(self._inventory_box, text)

    @staticmethod
    def _effective_targets(mod) -> set[str]:
        return expand_target_values(mod.targets)

    def _active_local_mods_dir(self) -> Optional[Path]:
        if self._source_var.get() == "server":
            return self.app.paths.server_mods
        return self.app.paths.dedicated_server_mods

    @staticmethod
    def _local_server_inventory_text(mods, label: str, snapshot: LiveModsFolderSnapshot) -> str:
        unmanaged_bundles = bundle_live_file_names(snapshot.unmanaged_files)
        lines = [f"Folder: {snapshot.folder or '(not configured)'}"]
        if snapshot.warning:
            lines.append(snapshot.warning)
        else:
            lines.append(
                f"{len(snapshot.live_files)} live file(s) | "
                f"{len(unmanaged_bundles)} unmanaged item(s) | "
                f"{len(snapshot.missing_managed_files)} missing managed"
            )
        lines.append("")
        if not mods:
            lines.append(f"No managed {label.lower()} installs are currently tracked.")
        else:
            lines.append(f"{len(mods)} managed install(s) for the {label.lower()}.")
            lines.append("")
        for mod in sorted(mods, key=lambda item: item.display_name.lower()):
            variant = f" ({mod.selected_variant})" if mod.selected_variant else ""
            status = "disabled" if not mod.enabled else "enabled"
            lines.append(f"{mod.display_name}{variant} [{status}]")
            lines.append(f"  archive: {Path(mod.source_archive).name if mod.source_archive else '(no archive)'}")
            lines.append(f"  files:   {mod.file_count}")
            lines.append("")
        if unmanaged_bundles:
            lines.append("Unmanaged items in ~mods:")
            for bundle in unmanaged_bundles:
                if bundle.file_count == 1:
                    lines.append(f"  {bundle.file_names[0]}")
                else:
                    lines.append(f"  {bundle.display_name} ({bundle.file_count} files)")
            lines.append("")
        if snapshot.missing_managed_files:
            lines.append("Managed files missing from ~mods:")
            lines.extend(f"  {name}" for name in snapshot.missing_managed_files)
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _hosted_server_inventory_text(remote_files: list[str]) -> str:
        if not remote_files:
            return "No files were found in the hosted mods folder."
        names = sorted(Path(path).name for path in remote_files)
        pak_names = [name for name in names if name.lower().endswith(".pak")]
        other_names = [name for name in names if name not in pak_names]
        lines = [f"{len(names)} file(s) found in the hosted mods folder.", ""]
        if pak_names:
            lines.append("PAK mods:")
            lines.extend(f"  {name}" for name in pak_names)
        if other_names:
            if pak_names:
                lines.append("")
            lines.append("Other files:")
            lines.extend(f"  {name}" for name in other_names)
        return "\n".join(lines).strip()

    def _set_status_box(self, box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _set_result(self, text: str, *, level: str = "info") -> None:
        colors = {
            "success": "#2d8a4e",
            "warning": "#e67e22",
            "error": "#c0392b",
            "info": "#95a5a6",
        }
        self._status_label.configure(text=text, text_color=colors.get(level, "#95a5a6"))

    def apply_ui_preferences(self) -> None:
        tokens = self.app.ui_tokens
        self._source_switch.configure(font=self.app.ui_font("body"), height=tokens.toolbar_button_height)
        self._remote_profile_label.configure(font=self.app.ui_font("body"))
        self._remote_profile_menu.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height)
        self._source_summary_label.configure(font=self.app.ui_font("body"), wraplength=tokens.panel_wrap)
        self._status_label.configure(font=self.app.ui_font("small"), wraplength=tokens.panel_wrap)
        self._dashboard_summary_label.configure(font=self.app.ui_font("body"), wraplength=tokens.panel_wrap)
        self._dashboard_counts_label.configure(font=self.app.ui_font("small"), wraplength=tokens.panel_wrap)
        self._server_hint_label.configure(font=self.app.ui_font("small"))
        self._world_info_label.configure(font=self.app.ui_font("small"))
        self._sync_hint_label.configure(font=self.app.ui_font("small"), wraplength=tokens.panel_wrap)
        self._confirm_check.configure(font=self.app.ui_font("body"))
        self._confirm_hint.configure(font=self.app.ui_font("small"), wraplength=tokens.panel_wrap)
        for label in self._field_labels:
            try:
                label.configure(font=self.app.ui_font("body"))
            except Exception:
                pass
        for field in self._field_inputs:
            try:
                field.configure(font=self.app.ui_font("body"))
            except Exception:
                pass
        for button in self._action_buttons:
            try:
                button.configure(font=self.app.ui_font("body"), height=tokens.compact_button_height)
            except Exception:
                pass
        for box in self._status_boxes:
            try:
                box.configure(font=self.app.ui_font("mono"))
            except Exception:
                pass

    def _ensure_apply_confirmation(self, prompt: str) -> bool:
        category = "hosted" if self._source_var.get() == "hosted" else "routine"
        if category != "hosted" and self._confirm_var.get():
            return True
        return self.app.confirm_action(
            category,
            "Confirm Apply",
            prompt + "\n\nA recovery backup will be created before writing changes.",
        )

    def _on_test_connection(self) -> None:
        if self._source_var.get() != "hosted":
            log.info("Hosted connection test skipped because a local server source is active")
            self._status_label.configure(
                text="Connection testing only applies to hosted server profiles.",
                text_color="#95a5a6",
            )
            return
        profile = self._selected_remote_profile()
        if profile is None:
            messagebox.showwarning("Hosted Profile Required", "Choose a hosted profile first.")
            return
        log.info("Testing hosted connection for profile: %s", profile.name)
        self._test_btn.configure(state="disabled", text="Testing...")
        self._status_label.configure(text=f"Testing hosted connection to {profile.name}...", text_color="#95a5a6")

        def _work() -> None:
            ok, message = self.app.remote_deployer.test_connection(profile)
            framework_text = "Unknown"
            if ok:
                framework_state = self.app.framework_state.remote_state(profile)
                framework_text = framework_state.summary if framework_state.checked else f"Unknown ({framework_state.warning})"
            log.info("Hosted connection result for %s: %s", profile.name, message)

            def _show() -> None:
                if not self.winfo_exists():
                    return
                self._test_btn.configure(state="normal", text="Test Connection")
                self._status_label.configure(text=message, text_color="#2d8a4e" if ok else "#c0392b")
                self._hosted_dashboard_state = "Connected" if ok else "Offline"
                self._hosted_framework_summary = framework_text
                self._hosted_dashboard_profile_id = profile.profile_id
                self._refresh_dashboard()

            self.app.dispatch_to_ui(_show)

        threading.Thread(target=_work, daemon=True).start()

    def compare_now(self) -> None:
        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                self._set_status_box(self._sync_box, "Choose a hosted profile first.")
                return
            self._set_status_box(self._sync_box, "Comparing client mods with hosted server files...")
            compare_target = self._source_var.get()

            def _work() -> None:
                try:
                    remote_files = self.app.remote_deployer.list_remote_files(profile)
                    report = self.app.server_sync.compare_hosted(self.app.manifest.list_mods(), remote_files)
                    text = self._sync_report_text(report)
                    def _show() -> None:
                        if self.winfo_exists():
                            self._set_status_box(self._sync_box, text)
                            self._remember_compare_report(report, compare_target)
                except Exception as exc:
                    text = f"Hosted comparison failed:\n{exc}"
                    def _show() -> None:
                        if self.winfo_exists():
                            self._set_status_box(self._sync_box, text)
                            self._remember_compare_error("Hosted compare failed", compare_target)
                self.app.dispatch_to_ui(_show)

            threading.Thread(target=_work, daemon=True).start()
            return

        compare_target = self._active_local_target()
        report = self.app.server_sync.compare_local(self.app.manifest.list_mods(), target=compare_target)
        self._set_status_box(self._sync_box, self._sync_report_text(report))
        self._remember_compare_report(report, compare_target)

    @staticmethod
    def _sync_report_text(report) -> str:
        if not report.items:
            return report.summary
        lines = [report.summary, ""]
        for item in report.items:
            lines.append(f"[{item.status}] {item.name}")
            if item.client_summary:
                lines.append(f"  client: {item.client_summary}")
            if item.server_summary:
                lines.append(f"  server: {item.server_summary}")
            if item.details:
                lines.append(f"  note:   {item.details}")
            lines.append("")
        return "\n".join(lines).strip()

    def _selected_remote_profile(self):
        profile_id = self._remote_profile_labels.get(self._remote_profile_var.get())
        if not profile_id:
            return None
        return self.app.remote_profiles.get_profile(profile_id)

    @staticmethod
    def _hosted_protocol_help(protocol: str) -> str:
        if normalize_remote_protocol(protocol) == "ftp":
            return (
                "Host / IP = only the FTP hostname from your provider panel, for example ms2084.gamedata.io. "
                "Use FTP Credentials and port 21. Do not use Query, Game, or RCON ports here."
            )
        return (
            "Host / IP = the SFTP hostname or LAN IP from your provider panel. "
            "Host Havoc may expose separate FTP Info and SFTP Info. Use the panel values exactly as shown."
        )

    @staticmethod
    def _hosted_restart_help(protocol: str) -> str:
        if normalize_remote_protocol(protocol) == "ftp":
            return "Restart commands are unavailable for FTP profiles. FTP supports file access only."
        return "Optional SFTP/SSH restart command to run after Apply and Restart."

    # ================================================================== Server handlers

    def _on_load_all(self) -> None:
        if self._source_var.get() == "hosted":
            self._load_all_remote_async()
            return
        self._load_server_config()
        self._load_world_config()

    def _load_all_remote_async(self) -> None:
        profile = self._selected_remote_profile()
        if profile is None:
            messagebox.showwarning("Hosted Profile Required", "Select a hosted profile first.")
            return

        self._load_btn.configure(state="disabled")
        self._status_label.configure(text=f"Loading hosted settings from {profile.name}...", text_color="#95a5a6")

        def _work() -> None:
            config = self.app.remote_config_svc.load_server(profile)
            world_config = None
            world_path = None
            if config and config.world_island_id:
                world_config, world_path = self.app.remote_config_svc.load_world_by_island_id(
                    profile,
                    config.world_island_id,
                )
            self.app.dispatch_to_ui(
                lambda: self.winfo_exists() and self._finish_remote_load(profile.name, config, world_config, world_path)
            )

        threading.Thread(target=_work, daemon=True).start()

    def _finish_remote_load(
        self,
        profile_name: str,
        config: Optional[ServerConfig],
        world_config: Optional[WorldConfig],
        world_path: Optional[str],
    ) -> None:
        self._load_btn.configure(state="normal")
        if config is None:
            self._config = None
            self._world_config = None
            self._world_path = None
            self._clear_server_fields()
            self._clear_world_fields()
            self._status_label.configure(text=f"Failed to load hosted settings from {profile_name}", text_color="#c0392b")
            self._hosted_dashboard_state = "Offline"
            self._hosted_framework_summary = "Unknown"
            messagebox.showerror(
                "Hosted Load Failed",
                "Failed to load hosted server settings.\n"
                "Check the profile connection details, server folder, and overrides.",
            )
            self._refresh_dashboard()
            return

        self._config = config
        self._populate_server_fields(config)
        self._status_label.configure(text=f"Hosted server settings loaded from {profile_name}", text_color="#2d8a4e")
        self._hosted_dashboard_state = "Connected"
        profile = self._selected_remote_profile()
        try:
            framework_state = self.app.framework_state.remote_state(profile) if profile else None
            self._hosted_framework_summary = framework_state.summary if framework_state and framework_state.checked else "Unknown"
        except Exception:
            self._hosted_framework_summary = "Unknown"
        self._hosted_dashboard_profile_id = profile.profile_id if profile else None

        if config.world_island_id:
            if world_config is not None and world_path is not None:
                self._world_config = world_config
                self._world_path = world_path
                self._populate_world_fields(world_config)
                world_label = self._world_display_name(world_config)
                self._world_info_label.configure(text=f'"{world_label}" - {world_config.world_preset_type}', text_color="#2d8a4e")
            else:
                self._world_config = None
                self._world_path = None
                self._clear_world_fields()
                self._world_info_label.configure(
                    text=f"(hosted world {config.world_island_id[:8]}... not found - check World Saves Folder Override)"
                )
        else:
            self._world_config = None
            self._world_path = None
            self._clear_world_fields()
        self._update_apply_summary()
        self._refresh_server_inventory()
        self.compare_now()
        self._refresh_dashboard()

    def _load_server_config(self) -> None:
        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                messagebox.showwarning("Hosted Profile Required", "Select a hosted profile first.")
                return
            config = self.app.remote_config_svc.load_server(profile)
            if config is None:
                messagebox.showerror(
                    "Error",
                    "Failed to load hosted server settings.\n"
                    "Check the hosted server folder and any overrides.",
                )
                return
            self._status_label.configure(text=f"Hosted server settings loaded from {profile.name}", text_color="#2d8a4e")
        else:
            label = self._active_local_label()
            desc_path = self._active_local_server_config_path()
            if not desc_path or not desc_path.is_file():
                messagebox.showwarning(
                    "Not Found",
                    "ServerDescription.json not found.\n"
                    f"Check the {label.lower()} path in Settings, then launch it once so it can create R5/ServerDescription.json.",
                )
                return

            config = self.app.server_config_svc.load(desc_path)
            if config is None:
                messagebox.showerror("Error", "Failed to load server config.")
                return

            self._status_label.configure(text=f"{label} settings loaded", text_color="#2d8a4e")

        self._config = config
        self._populate_server_fields(config)
        self._update_apply_summary()
        self._refresh_server_inventory()
        log.info("Server config loaded")

    def _populate_server_fields(self, cfg: ServerConfig) -> None:
        mapping = {
            "ServerName": cfg.server_name,
            "InviteCode": cfg.invite_code,
            "IsPasswordProtected": cfg.is_password_protected,
            "Password": cfg.password,
            "MaxPlayerCount": str(cfg.max_player_count),
            "WorldIslandId": cfg.world_island_id,
            "P2pProxyAddress": cfg.p2p_proxy_address,
            "DeploymentId": cfg.deployment_id,
            "PersistentServerId": cfg.persistent_server_id,
        }
        for key, value in mapping.items():
            widget = self._fields[key]
            var = widget._variable
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            else:
                was_readonly = False
                try:
                    if widget.cget("state") == "readonly":
                        was_readonly = True
                        widget.configure(state="normal")
                except Exception:
                    pass
                var.set(str(value))
                if was_readonly:
                    widget.configure(state="readonly")

    def _clear_server_fields(self) -> None:
        for key, widget in self._fields.items():
            var = widget._variable
            if isinstance(var, tk.BooleanVar):
                var.set(False)
            else:
                was_readonly = False
                try:
                    if widget.cget("state") == "readonly":
                        was_readonly = True
                        widget.configure(state="normal")
                except Exception:
                    pass
                var.set("")
                if was_readonly:
                    widget.configure(state="readonly")

    def _read_server_fields(self) -> ServerConfig:
        cfg = self._config or ServerConfig()
        cfg.server_name = self._fields["ServerName"]._variable.get()
        cfg.invite_code = self._fields["InviteCode"]._variable.get()
        cfg.is_password_protected = self._fields["IsPasswordProtected"]._variable.get()
        cfg.password = self._fields["Password"]._variable.get()
        try:
            cfg.max_player_count = int(self._fields["MaxPlayerCount"]._variable.get())
        except ValueError:
            cfg.max_player_count = 0
        cfg.p2p_proxy_address = self._fields["P2pProxyAddress"]._variable.get()
        return cfg

    def _on_save_server(self, *, notify_success: bool = True) -> bool:
        if not self._ensure_apply_confirmation("Apply server settings for the current source?"):
            return False

        config = self._read_server_fields()
        errors = config.validate()
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return False

        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                messagebox.showerror("Error", "Select a hosted profile first.")
                return False
            success, save_errors = self.app.remote_config_svc.save_server(profile, config)
        else:
            label = self._active_local_label()
            target = self._active_local_target()
            desc_path = self._active_local_server_config_path()
            if not desc_path:
                messagebox.showerror("Error", f"{label} path not configured.")
                return False
            success, save_errors = self.app.server_config_svc.save(desc_path, config)
        if success:
            if self._source_var.get() == "hosted":
                self._status_label.configure(text="Hosted server settings saved", text_color="#2d8a4e")
                self._record_action(
                    action="save_remote_server_config",
                    target="hosted",
                    notes=f"Saved hosted server settings for {config.server_name or profile.name}",
                )
            else:
                self._status_label.configure(text=f"{label} settings saved", text_color="#2d8a4e")
                self._record_action(
                    action="save_server_config",
                    target=target,
                    notes=f"Saved {label.lower()} settings for {config.server_name or 'server'}",
                )
            self._confirm_var.set(False)
            self._update_apply_summary()
            if notify_success:
                self._set_result("Server configuration saved. A backup was created.", level="success")
            return True
        else:
            messagebox.showerror("Save Failed", "\n".join(save_errors))
            return False

    def _on_restore_server(self) -> None:
        if not self.app.confirm_action(
            "destructive",
            "Restore Previous Version",
            "Restore the most recent server config backup for the current source?",
        ):
            return

        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                messagebox.showerror("Error", "Select a hosted profile first.")
                return
            restored = self.app.remote_config_svc.restore_latest_server(profile)
        else:
            label = self._active_local_label()
            desc_path = self._active_local_server_config_path()
            if not desc_path:
                messagebox.showerror("Error", f"{label} path not configured.")
                return
            restored = self.app.server_config_svc.restore_latest(desc_path)

        if restored:
            self._status_label.configure(text="Restored from backup")
            self._on_load_all()
        else:
            messagebox.showwarning("No Backup", "No matching server config backups found.")

    # ================================================================== World handlers

    def _load_world_config(self) -> None:
        if not self._config:
            self._world_info_label.configure(text="(load server config first)")
            return

        island_id = self._config.world_island_id
        if not island_id:
            self._world_info_label.configure(text="(no WorldIslandId set)")
            return

        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                self._world_info_label.configure(text="(select a hosted profile)")
                return
            config, world_path = self.app.remote_config_svc.load_world_by_island_id(profile, island_id)
            if world_path is None or config is None:
                self._world_info_label.configure(
                    text=f"(hosted world {island_id[:8]}... not found - check World Saves Folder Override)"
                )
                log.warning("Could not find hosted WorldDescription.json for island %s", island_id)
                return
        else:
            world_path = self.app.world_config_svc.find_world_by_island_id(
                island_id, self._active_local_save_root(),
            )
            if world_path is None:
                label = self._active_local_label()
                self._world_info_label.configure(
                    text=(
                        f"(world {island_id[:8]}... not found - start the {label.lower()} once or review "
                        f"{self._active_local_world_hint()})"
                    )
                )
                log.warning("Could not find WorldDescription.json for island %s", island_id)
                return

            config = self.app.world_config_svc.load(world_path)
            if config is None:
                self._world_info_label.configure(text="(failed to load)")
                return

        self._world_config = config
        self._world_path = world_path
        self._populate_world_fields(config)
        self._world_info_label.configure(
            text=f'"{config.world_name}" — {config.world_preset_type}',
            text_color="#2d8a4e",
        )
        world_label = self._world_display_name(config)
        self._world_info_label.configure(text=f'"{world_label}" - {config.world_preset_type}', text_color="#2d8a4e")
        self._update_apply_summary()
        log.info("World config loaded: %s", config.world_name)

    def _populate_world_fields(self, cfg: WorldConfig) -> None:
        # World name
        w = self._world_fields["WorldName"]
        w._variable.set(cfg.world_name)

        # Preset
        self._preset_var.set(cfg.world_preset_type)

        # Combat difficulty
        display = _CD_DISPLAY.get(cfg.combat_difficulty, "Normal")
        self._combat_diff_var.set(display)

        # Bool params
        for tag_key in BOOL_PARAM_SPEC:
            field_key = f"bool_{tag_key}"
            if field_key in self._world_fields:
                value = cfg.bool_params.get(tag_key, BOOL_PARAM_SPEC[tag_key][1])
                self._world_fields[field_key]._variable.set(value)

        # Float params
        for tag_key in FLOAT_PARAM_SPEC:
            field_key = f"float_{tag_key}"
            if field_key in self._world_fields:
                slider, value_var = self._world_fields[field_key]
                value = cfg.float_params.get(tag_key, FLOAT_PARAM_SPEC[tag_key][1])
                slider.set(value)
                value_var.set(f"{value:.2f}")

    def _clear_world_fields(self) -> None:
        w = self._world_fields["WorldName"]
        w._variable.set("")

        self._preset_var.set("Medium")
        self._combat_diff_var.set("Normal")

        for tag_key, (_, default) in BOOL_PARAM_SPEC.items():
            fk = f"bool_{tag_key}"
            if fk in self._world_fields:
                self._world_fields[fk]._variable.set(default)

        for tag_key, (_, default, _, _) in FLOAT_PARAM_SPEC.items():
            fk = f"float_{tag_key}"
            if fk in self._world_fields:
                slider, value_var = self._world_fields[fk]
                slider.set(default)
                value_var.set(f"{default:.2f}")

        self._world_info_label.configure(text="(not loaded)", text_color="#95a5a6")

    def _read_world_fields(self) -> WorldConfig:
        cfg = self._world_config or WorldConfig()
        cfg.world_name = self._world_fields["WorldName"]._variable.get()

        cfg.world_preset_type = self._preset_var.get()
        cfg.combat_difficulty = _CD_FROM_DISPLAY.get(
            self._combat_diff_var.get(),
            "WDS.Parameter.CombatDifficulty.Normal",
        )

        for tag_key in BOOL_PARAM_SPEC:
            field_key = f"bool_{tag_key}"
            if field_key in self._world_fields:
                cfg.bool_params[tag_key] = self._world_fields[field_key]._variable.get()

        for tag_key in FLOAT_PARAM_SPEC:
            field_key = f"float_{tag_key}"
            if field_key in self._world_fields:
                _, value_var = self._world_fields[field_key]
                try:
                    cfg.float_params[tag_key] = float(value_var.get())
                except ValueError:
                    cfg.float_params[tag_key] = FLOAT_PARAM_SPEC[tag_key][1]

        return cfg

    def _on_preset_change(self, value: str) -> None:
        """When preset changes from Custom to a named preset, reset params to defaults."""
        if value == "Custom":
            return
        # For non-custom presets, the game applies defaults on next launch,
        # so clear custom settings to defaults
        for tag_key, (_, default) in BOOL_PARAM_SPEC.items():
            fk = f"bool_{tag_key}"
            if fk in self._world_fields:
                self._world_fields[fk]._variable.set(default)
        for tag_key, (_, default, lo, hi) in FLOAT_PARAM_SPEC.items():
            fk = f"float_{tag_key}"
            if fk in self._world_fields:
                slider, value_var = self._world_fields[fk]
                slider.set(default)
                value_var.set(f"{default:.2f}")
        self._combat_diff_var.set("Normal")

    def _on_save_world(self, *, notify_success: bool = True) -> bool:
        if not self._ensure_apply_confirmation("Apply world settings for the current source?"):
            return False

        if not self._world_path:
            messagebox.showerror("Error", "No world loaded. Click 'Load All' first.")
            return False

        config = self._read_world_fields()
        errors = config.validate()
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return False

        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                messagebox.showerror("Error", "Select a hosted profile first.")
                return False
            success, save_errors = self.app.remote_config_svc.save_world(profile, str(self._world_path), config)
        else:
            success, save_errors = self.app.world_config_svc.save(self._world_path, config)
        if success:
            self._status_label.configure(
                text="Hosted world settings saved" if self._source_var.get() == "hosted"
                else f"{self._active_local_label()} world settings saved",
                text_color="#2d8a4e",
            )
            if self._source_var.get() == "hosted":
                self._record_action(
                    action="save_remote_world_config",
                    target="hosted",
                    notes=f"Saved hosted world settings for {config.world_name}",
                )
            else:
                label = self._active_local_label()
                self._record_action(
                    action="save_world_config",
                    target=self._active_local_target(),
                    notes=f"Saved {label.lower()} world settings for {config.world_name}",
                )
            self._confirm_var.set(False)
            self._update_apply_summary()
            if notify_success:
                self._set_result(
                    f'World settings for "{config.world_name}" saved. A backup was created.',
                    level="success",
                )
            return True
        else:
            messagebox.showerror("Save Failed", "\n".join(save_errors))
            return False

    def _on_restore_world(self) -> None:
        if not self._world_path:
            self._set_result("Load world settings first.", level="info")
            return
        if not self.app.confirm_action(
            "destructive",
            "Restore Previous Version",
            "Restore the most recent world settings backup?",
        ):
            return
        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                messagebox.showerror("Error", "Select a hosted profile first.")
                return
            restored = self.app.remote_config_svc.restore_latest_world(profile, str(self._world_path))
        else:
            latest = self.app.backup.latest_backup(category="world_config", source_path=self._world_path)
            restored = self.app.backup.restore_backup(latest, dest_path=Path(self._world_path)) if latest else False
        if restored:
            self._status_label.configure(text="Restored world settings from backup")
            self._on_load_all()
        else:
            messagebox.showwarning("No Backup", "No matching world backups were found.")

    def _on_apply_changes(self) -> bool:
        temporary_confirm = False
        if not self._confirm_var.get():
            if not self._ensure_apply_confirmation("Apply all loaded server and world changes?"):
                return False
            self._confirm_var.set(True)
            temporary_confirm = True
        if not self._config and not self._world_path:
            if temporary_confirm:
                self._confirm_var.set(False)
            self._set_result("Load current settings first.", level="info")
            return False
        original_confirm = self._confirm_var.get()
        save_ok = True
        if self._config:
            save_ok = self._on_save_server(notify_success=False)
        if save_ok and self._world_path:
            self._confirm_var.set(original_confirm)
            save_ok = self._on_save_world(notify_success=False)
        if temporary_confirm:
            self._confirm_var.set(False)
        self._update_apply_summary()
        if save_ok:
            self._set_result("Loaded changes were applied successfully. Backup copies were created.", level="success")
        return save_ok

    def _on_apply_and_restart(self) -> None:
        if not self._on_apply_changes():
            return
        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                return
            ok, message = self.app.remote_deployer.restart_remote(profile)
            self._status_label.configure(text=message, text_color="#2d8a4e" if ok else "#c0392b")
            if ok:
                self._record_action(
                    action="hosted_restart",
                    target="hosted",
                    notes=f"Ran hosted restart command for {profile.name}",
                )
        else:
            label = self._active_local_label()
            if self.app._launch_server_root(self._active_local_root(), label=label):
                self._status_label.configure(
                    text=f"Launched {label.lower()} after applying changes.",
                    text_color="#2d8a4e",
                )
            else:
                self._status_label.configure(
                    text=f"{label} launch failed after apply.",
                    text_color="#c0392b",
                )

    def _record_action(self, *, action: str, target: str, notes: str) -> None:
        self.app.manifest.add_record(
            DeploymentRecord(
                mod_id=f"server:{target}",
                action=action,
                target=target,
                notes=notes,
                display_name="Server Settings",
            )
        )
        self.app.dispatch_to_ui(lambda: self.app.refresh_backups_tab())

    def _record_hosted_upload(self, *, archive_path, display_name: str, profile: RemoteProfile, plan, result, notes: str) -> None:
        uploaded_paths = set(getattr(result, "uploaded", []) or [])
        files = [
            DeployedFile(source_archive_path=item.archive_entry_path, dest_path=item.remote_path)
            for item in getattr(plan, "files", [])
            if not uploaded_paths or item.remote_path in uploaded_paths
        ]
        if not files:
            files = [DeployedFile(source_archive_path="", dest_path=path) for path in uploaded_paths]
        archive_text = str(archive_path or "")
        archive_stem = Path(archive_text).stem if archive_text else (display_name or "Hosted Upload")
        self.app.manifest.add_record(
            DeploymentRecord(
                mod_id=f"hosted:{profile.profile_id}:{archive_stem}",
                action="hosted_upload",
                target="hosted",
                display_name=display_name or archive_stem,
                source_archive=archive_text,
                install_kind=getattr(plan, "install_kind", "standard_mod"),
                files=files,
                notes=notes,
            )
        )
        self.app.dispatch_to_ui(lambda: self.app.refresh_backups_tab())

    def open_hosted_setup(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Hosted Server Setup")
        self.app.center_dialog(dialog, 580, 700)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        self._hosted_setup_dialog = dialog
        body = ctk.CTkScrollableFrame(dialog)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.grid_columnconfigure(0, weight=1)

        current = self._selected_remote_profile() or RemoteProfile.new("Hosted Server")
        vars_map = {
            "name": ctk.StringVar(value=current.name),
            "protocol": ctk.StringVar(value=normalize_remote_protocol(current.protocol)),
            "host": ctk.StringVar(value=current.host),
            "port": ctk.StringVar(value=str(current.port)),
            "username": ctk.StringVar(value=current.username),
            "password": ctk.StringVar(value=current.password),
            "key": ctk.StringVar(value=current.private_key_path),
            "root": ctk.StringVar(value=current.remote_root_dir),
            "mods": ctk.StringVar(value=current.remote_mods_dir),
            "server_desc": ctk.StringVar(value=current.remote_server_description_path),
            "save_root": ctk.StringVar(value=current.remote_save_root),
            "restart": ctk.StringVar(value=current.restart_command),
        }
        auth_var = ctk.StringVar(value=current.auth_mode or "password")
        ctk.CTkLabel(body, text="Hosted Server Setup", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 6)
        )
        ctk.CTkLabel(
            body,
            text=(
                "Start with the hosted server folder. The manager can derive the Windrose mods folder, "
                "server settings file, and world saves folder from it. If your login already opens inside "
                "the Windrose server folder, you can enter '.' here or leave it blank and fill the overrides manually."
            ),
            justify="left",
            wraplength=520,
            text_color="#95a5a6",
        ).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 10))

        connection = ctk.CTkFrame(body)
        connection.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        connection.grid_columnconfigure(1, weight=1)
        connection.grid_columnconfigure(3, weight=0)
        ctk.CTkLabel(connection, text="Connection", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(12, 8)
        )
        ctk.CTkLabel(connection, text="Profile Name:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        ctk.CTkEntry(connection, textvariable=vars_map["name"]).grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=8, pady=4
        )
        ctk.CTkLabel(connection, text="Protocol:").grid(row=2, column=0, sticky="w", padx=12, pady=4)
        protocol_menu = ctk.CTkOptionMenu(
            connection,
            variable=vars_map["protocol"],
            values=list(SUPPORTED_REMOTE_PROTOCOLS),
            width=120,
        )
        protocol_menu.grid(row=2, column=1, sticky="w", padx=8, pady=4)
        ctk.CTkLabel(connection, text="Host / IP:").grid(row=3, column=0, sticky="w", padx=12, pady=4)
        ctk.CTkEntry(connection, textvariable=vars_map["host"]).grid(row=3, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(connection, text="Port:").grid(row=3, column=2, sticky="w", padx=(8, 4), pady=4)
        ctk.CTkEntry(connection, textvariable=vars_map["port"], width=86).grid(row=3, column=3, sticky="e", padx=(0, 12), pady=4)
        protocol_hint_label = ctk.CTkLabel(
            connection,
            text="",
            justify="left",
            wraplength=310,
            text_color="#95a5a6",
        )
        protocol_hint_label.grid(row=4, column=1, columnspan=3, sticky="ew", padx=8, pady=(0, 4))
        ctk.CTkEntry(connection, textvariable=vars_map["username"]).grid(
            row=5, column=1, columnspan=3, sticky="ew", padx=8, pady=4
        )
        ctk.CTkLabel(connection, text="Username:").grid(row=5, column=0, sticky="w", padx=12, pady=4)
        auth_mode_label = ctk.CTkLabel(connection, text="Auth Mode:")
        auth_mode_label.grid(row=6, column=0, sticky="w", padx=12, pady=4)
        auth_menu = ctk.CTkOptionMenu(connection, variable=auth_var, values=["password", "key"], width=120)
        auth_menu.grid(row=6, column=1, sticky="w", padx=8, pady=4)
        auth_hint_label = ctk.CTkLabel(
            connection,
            text="Use password for hosting-panel accounts or a private key for OpenSSH/SFTP logins.",
            justify="left",
            wraplength=310,
            text_color="#95a5a6",
        )
        auth_hint_label.grid(row=6, column=2, columnspan=2, sticky="ew", padx=(8, 12), pady=4)
        ctk.CTkLabel(connection, text="Password:").grid(row=7, column=0, sticky="w", padx=12, pady=4)
        password_entry = ctk.CTkEntry(connection, textvariable=vars_map["password"], show="*")
        password_entry.grid(row=7, column=1, columnspan=3, sticky="ew", padx=8, pady=4)
        key_label = ctk.CTkLabel(connection, text="Private Key:")
        key_label.grid(row=8, column=0, sticky="w", padx=12, pady=4)
        key_row = ctk.CTkFrame(connection, fg_color="transparent")
        key_row.grid(row=8, column=1, columnspan=3, sticky="ew", padx=8, pady=4)
        key_row.grid_columnconfigure(0, weight=1)
        key_entry = ctk.CTkEntry(key_row, textvariable=vars_map["key"])
        key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        key_browse_btn = ctk.CTkButton(
            key_row,
            text="Browse",
            width=76,
            command=lambda: vars_map["key"].set(
                filedialog.askopenfilename(title="Select Private Key") or vars_map["key"].get()
            ),
        )
        key_browse_btn.grid(row=0, column=1, sticky="e")

        root_card = ctk.CTkFrame(body)
        root_card.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        root_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(root_card, text="Server Folder", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8)
        )
        ctk.CTkLabel(root_card, text="Server Folder:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        ctk.CTkEntry(root_card, textvariable=vars_map["root"]).grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(
            root_card,
            text="Example: /home/container, C:/Games/WindroseServer, or '.' when the login already lands inside the server folder",
            justify="left",
            text_color="#95a5a6",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))

        overrides = ctk.CTkFrame(body)
        overrides.grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 8))
        overrides.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(overrides, text="Advanced Overrides", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8)
        )
        ctk.CTkLabel(
            overrides,
            text="Leave these blank unless your host uses non-standard paths.",
            justify="left",
            wraplength=520,
            text_color="#95a5a6",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))
        advanced_fields = [
            ("Mods Folder Override", "mods"),
            ("Server Settings File Override", "server_desc"),
            ("World Saves Folder Override", "save_root"),
        ]
        for row, (label, key) in enumerate(advanced_fields, start=2):
            ctk.CTkLabel(overrides, text=label + ":").grid(row=row, column=0, sticky="w", padx=12, pady=4)
            ctk.CTkEntry(overrides, textvariable=vars_map[key]).grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        restart_label = ctk.CTkLabel(overrides, text="Restart Command:")
        restart_label.grid(row=5, column=0, sticky="w", padx=12, pady=4)
        restart_entry = ctk.CTkEntry(overrides, textvariable=vars_map["restart"])
        restart_entry.grid(row=5, column=1, sticky="ew", padx=8, pady=4)
        restart_hint_label = ctk.CTkLabel(
            overrides,
            text="",
            justify="left",
            wraplength=520,
            text_color="#95a5a6",
        )
        restart_hint_label.grid(row=6, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))

        status = ctk.CTkLabel(body, text="", text_color="#95a5a6", justify="left", wraplength=520)
        status.grid(row=5, column=0, sticky="ew", padx=8, pady=(4, 8))

        provider_card = ctk.CTkFrame(body)
        provider_card.grid(row=6, column=0, sticky="ew", padx=8, pady=(0, 8))
        provider_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(provider_card, text="Provider Shortcuts", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 4)
        )
        ctk.CTkLabel(
            provider_card,
            text=(
                "These only set the protocol and normal default port. For Nitrado, use the FTP Credentials "
                "hostname, username, password, and port 21. Query/RCON/Game ports are not FTP ports."
            ),
            justify="left",
            wraplength=520,
            text_color="#95a5a6",
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        preset_buttons = ctk.CTkFrame(provider_card, fg_color="transparent")
        preset_buttons.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 12))

        def _build_profile() -> RemoteProfile:
            host, port, resolved_protocol = normalize_remote_endpoint(
                vars_map["host"].get().strip(),
                vars_map["port"].get().strip(),
                protocol=vars_map["protocol"].get(),
            )
            profile = RemoteProfile(
                profile_id=current.profile_id,
                name=vars_map["name"].get().strip() or "Hosted Server",
                protocol=resolved_protocol,
                host=host,
                port=port,
                username=vars_map["username"].get().strip(),
                auth_mode=auth_var.get() if resolved_protocol == "sftp" else "password",
                password=vars_map["password"].get(),
                private_key_path=vars_map["key"].get().strip() if resolved_protocol == "sftp" else "",
                remote_root_dir=vars_map["root"].get().strip(),
                remote_mods_dir=vars_map["mods"].get().strip(),
                remote_server_description_path=vars_map["server_desc"].get().strip(),
                remote_save_root=vars_map["save_root"].get().strip(),
                restart_command=vars_map["restart"].get().strip() if resolved_protocol == "sftp" else "",
            )
            profile.apply_root_defaults(overwrite=False)
            return profile

        last_diagnostics = {"text": ""}

        def _diagnostics_text(profile: RemoteProfile, result: str = "") -> str:
            lines = [
                "Windrose hosted connection diagnostics",
                remote_connection_diagnostics(profile),
            ]
            if result.strip():
                lines.append("")
                lines.append("Last result:")
                lines.append(result.strip())
            if normalize_remote_protocol(profile.protocol) == "ftp":
                lines.extend(
                    [
                        "",
                        "FTP note: use provider FTP Credentials. Nitrado Query/RCON/Game ports are not FTP ports.",
                        f"PowerShell reachability check: Test-NetConnection {profile.host} -Port {profile.port}",
                    ]
                )
            return "\n".join(lines)

        def _copy_diagnostics() -> None:
            try:
                profile = _build_profile()
            except ValueError:
                messagebox.showerror("Invalid Endpoint", "Host / IP and port must be valid.")
                return
            text = last_diagnostics["text"] or _diagnostics_text(profile)
            dialog.clipboard_clear()
            dialog.clipboard_append(text)
            status.configure(text="Hosted diagnostics copied without password/private-key contents.", text_color="#2d8a4e")

        def _apply_profile_fields(profile: RemoteProfile) -> None:
            vars_map["protocol"].set(normalize_remote_protocol(profile.protocol))
            vars_map["host"].set(profile.host)
            vars_map["port"].set(str(profile.port))
            vars_map["root"].set(profile.remote_root_dir)
            vars_map["mods"].set(profile.remote_mods_dir)
            vars_map["server_desc"].set(profile.remote_server_description_path)
            vars_map["save_root"].set(profile.remote_save_root)
            vars_map["restart"].set(profile.restart_command)
            if profile.supports_key_auth():
                auth_var.set(profile.auth_mode or "password")
                vars_map["key"].set(profile.private_key_path)
            else:
                auth_var.set("password")
                vars_map["key"].set("")

        def _apply_root_defaults(overwrite: bool = True) -> None:
            try:
                profile = _build_profile()
            except ValueError:
                messagebox.showerror("Invalid Endpoint", "Host / IP and port must be valid.")
                return
            if not profile.remote_root_dir.strip():
                status.configure(text="Enter the hosted server folder first.", text_color="#c0392b")
                return
            profile.apply_root_defaults(overwrite=overwrite)
            _apply_profile_fields(profile)
            status.configure(
                text="Derived Windrose hosted paths from the server folder. Review them before saving.",
                text_color="#2d8a4e",
            )

        def _apply_provider_preset(protocol: str, port: int, label: str) -> None:
            previous_port = vars_map["port"].get().strip()
            default_ports = {"", str(default_port_for_protocol("sftp")), str(default_port_for_protocol("ftp"))}
            vars_map["protocol"].set(protocol)
            if previous_port in default_ports:
                vars_map["port"].set(str(port))
                port_note = f"port {port}"
            else:
                port_note = f"kept explicit port {previous_port}"
            status.configure(
                text=f"{label} preset applied ({protocol.upper()}, {port_note}). Fill in the provider host and credentials from your panel.",
                text_color="#2d8a4e",
            )

        sync_state = {"last_protocol": normalize_remote_protocol(vars_map["protocol"].get())}

        def _sync_auth_fields(*_args) -> None:
            protocol = normalize_remote_protocol(vars_map["protocol"].get())
            is_ftp = protocol == "ftp"
            is_key = auth_var.get() == "key" and not is_ftp
            protocol_hint_label.configure(text=self._hosted_protocol_help(protocol))
            restart_hint_label.configure(text=self._hosted_restart_help(protocol))
            previous_protocol = sync_state["last_protocol"]
            previous_default = str(default_port_for_protocol(previous_protocol))
            if (not vars_map["port"].get().strip()) or vars_map["port"].get().strip() == previous_default:
                vars_map["port"].set(str(default_port_for_protocol(protocol)))
            sync_state["last_protocol"] = protocol

            if is_ftp:
                if auth_var.get() != "password":
                    auth_var.set("password")
                if auth_mode_label.winfo_manager():
                    auth_mode_label.grid_remove()
                if auth_menu.winfo_manager():
                    auth_menu.grid_remove()
                if auth_hint_label.winfo_manager():
                    auth_hint_label.grid_remove()
                if key_label.winfo_manager():
                    key_label.grid_remove()
                if key_row.winfo_manager():
                    key_row.grid_remove()
                password_entry.configure(state="normal")
                key_entry.configure(state="disabled")
                key_browse_btn.configure(state="disabled")
                restart_entry.configure(state="disabled")
            else:
                if not auth_mode_label.winfo_manager():
                    auth_mode_label.grid()
                if not auth_menu.winfo_manager():
                    auth_menu.grid()
                if not auth_hint_label.winfo_manager():
                    auth_hint_label.grid()
                if not key_label.winfo_manager():
                    key_label.grid()
                if not key_row.winfo_manager():
                    key_row.grid()
                password_entry.configure(state="disabled" if is_key else "normal")
                key_entry.configure(state="normal" if is_key else "disabled")
                key_browse_btn.configure(state="normal" if is_key else "disabled")
                restart_entry.configure(state="normal")

        def _save() -> None:
            try:
                profile = _build_profile()
            except ValueError:
                messagebox.showerror("Invalid Endpoint", "Host / IP and port must be valid.")
                return
            _apply_profile_fields(profile)
            self.app.remote_profiles.upsert(profile)
            self.refresh_remote_profiles()
            for label, profile_id in self._remote_profile_labels.items():
                if profile_id == profile.profile_id:
                    self._remote_profile_var.set(label)
                    break
            self._source_switch.set("Hosted Server")
            self._on_source_changed("hosted")
            status.configure(text=f"Saved profile '{profile.name}'.", text_color="#2d8a4e")

        def _test() -> None:
            try:
                profile = _build_profile()
            except ValueError:
                messagebox.showerror("Invalid Endpoint", "Host / IP and port must be valid.")
                return
            _apply_profile_fields(profile)
            status.configure(text="Testing hosted connection...", text_color="#95a5a6")

            def _work() -> None:
                ok, message = self.app.remote_deployer.test_connection(profile)
                diagnostics_text = _diagnostics_text(profile, message)

                def _show_result() -> None:
                    if not status.winfo_exists():
                        return
                    last_diagnostics["text"] = diagnostics_text
                    copy_diagnostics_btn.configure(state="normal")
                    status.configure(
                        text=message,
                        text_color="#2d8a4e" if ok else "#c0392b",
                    )

                self.app.dispatch_to_ui(_show_result)

            threading.Thread(target=_work, daemon=True).start()

        ctk.CTkButton(
            preset_buttons,
            text="Host Havoc SFTP",
            width=132,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: _apply_provider_preset("sftp", 22, "Host Havoc SFTP"),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            preset_buttons,
            text="Host Havoc FTP",
            width=126,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: _apply_provider_preset("ftp", 21, "Host Havoc FTP"),
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            preset_buttons,
            text="Indifferent Broccoli FTP",
            width=180,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: _apply_provider_preset("ftp", 21, "Indifferent Broccoli FTP"),
        ).pack(side="left", padx=6)

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.grid(row=7, column=0, sticky="ew", padx=8, pady=(4, 8))
        ctk.CTkButton(
            buttons,
            text="Auto-Detect Paths",
            width=146,
            fg_color="#555555",
            hover_color="#666666",
            command=_apply_root_defaults,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(buttons, text="Test Connection", width=120, command=_test).pack(side="left", padx=6)
        copy_diagnostics_btn = ctk.CTkButton(
            buttons,
            text="Copy Diagnostics",
            width=140,
            fg_color="#555555",
            hover_color="#666666",
            command=_copy_diagnostics,
        )
        copy_diagnostics_btn.pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Save Profile", width=110, fg_color="#2d8a4e", hover_color="#236b3d", command=_save).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Close", width=100, fg_color="#444444", hover_color="#555555", command=dialog.destroy).pack(side="right")
        vars_map["protocol"].trace_add("write", _sync_auth_fields)
        auth_var.trace_add("write", _sync_auth_fields)
        _sync_auth_fields()

    def open_hosted_install_dialog(self, archive_path: str | Path | None) -> None:
        selected_path = Path(archive_path) if archive_path else None
        if selected_path is None:
            active = self.app._mods_tab.selected_archive_path()
            selected_path = Path(active) if active else None
        if selected_path is None or not selected_path.is_file():
            self._set_result("Choose an archive in Library first.", level="info")
            return
        profile = self._selected_remote_profile()
        if profile is None:
            self._set_result("Set up a hosted profile first.", level="info")
            self.open_hosted_setup()
            return

        log.info("Opening hosted install dialog for %s", selected_path.name)
        info = inspect_archive(selected_path)
        dialog = ctk.CTkToplevel(self)
        dialog.title("Install to Hosted Server")
        self.app.center_dialog(dialog, 500, 400)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        self._hosted_install_dialog = dialog

        body = ctk.CTkFrame(dialog)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(4, weight=1)
        ctk.CTkLabel(body, text="Install to Hosted Server", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 12)
        )
        ctk.CTkLabel(body, text="Hosted Profile:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        profile_var = ctk.StringVar(value=self._remote_profile_var.get())
        profile_menu = ctk.CTkOptionMenu(body, variable=profile_var, values=list(self._remote_profile_labels.keys()) or ["(no remote profiles)"])
        profile_menu.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(body, text="Archive:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ctk.CTkLabel(body, text=selected_path.name, anchor="w").grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(body, text="Variant:").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        variant_names = [name for group in info.variant_groups for name in group.variant_names] or ["(none)"]
        variant_var = ctk.StringVar(value=variant_names[0])
        variant_menu = ctk.CTkOptionMenu(body, variable=variant_var, values=variant_names)
        variant_menu.grid(row=3, column=1, sticky="ew", padx=8, pady=4)
        preview = ctk.CTkTextbox(body, height=220, font=ctk.CTkFont(family="Consolas", size=11))
        preview.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=8, pady=(8, 8))
        preview_lines = [
            f"Archive: {selected_path.name}",
            f"Type: {info.archive_type.value}",
            f"Install kind: {info.install_kind.replace('_', ' ')}",
            f"Files: {info.total_files}",
        ]
        if info.likely_destinations:
            preview_lines.append(f"Destination: {', '.join(info.likely_destinations)}")
        if info.warnings or info.dependency_warnings:
            preview_lines.append("")
            preview_lines.extend(info.warnings)
            preview_lines.extend(info.dependency_warnings)
        preview.insert("1.0", "\n".join(preview_lines) + "\n")
        preview.configure(state="disabled")
        status = ctk.CTkLabel(body, text="", text_color="#95a5a6", justify="left", wraplength=470)
        status.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 8))
        deploy_btn = ctk.CTkButton(
            buttons,
            text="Install to Hosted Server",
            width=156,
            fg_color="#2980b9",
            hover_color="#2471a3",
        )

        def _deploy() -> None:
            chosen_profile = self.app.remote_profiles.get_profile(self._remote_profile_labels.get(profile_var.get(), ""))
            if chosen_profile is None:
                messagebox.showwarning("Hosted Profile Required", "Choose a hosted profile first.")
                return
            selected_variant = None if variant_var.get() == "(none)" else variant_var.get()
            plan = plan_remote_deployment(info, chosen_profile, selected_variant=selected_variant, mod_name=selected_path.stem)
            if not plan.valid:
                messagebox.showerror("Hosted Install Error", "\n".join(plan.warnings))
                return
            log.info("Uploading %s to hosted server profile %s", selected_path.name, chosen_profile.name)
            status.configure(text="Uploading to hosted server...", text_color="#95a5a6")
            self._status_label.configure(text=f"Uploading {selected_path.name} to hosted server...", text_color="#95a5a6")
            deploy_btn.configure(state="disabled", text="Installing...")

            def _work() -> None:
                try:
                    result = self.app.remote_deployer.deploy(plan, chosen_profile)
                    log.info(
                        "Hosted install result for %s on %s: %s",
                        selected_path.name,
                        chosen_profile.name,
                        result.summary,
                    )
                    self._record_hosted_upload(
                        archive_path=selected_path,
                        display_name=selected_path.stem,
                        profile=chosen_profile,
                        plan=plan,
                        result=result,
                        notes=f"Uploaded {selected_path.name} to hosted server {chosen_profile.name} ({result.summary})",
                    )
                    message = result.summary
                    def _show() -> None:
                        if not deploy_btn.winfo_exists() or not status.winfo_exists():
                            return
                        deploy_btn.configure(state="normal", text="Install to Hosted Server")
                        status.configure(text=message, text_color="#2d8a4e" if not result.failed else "#e67e22")
                        self._status_label.configure(text=message, text_color="#2d8a4e" if not result.failed else "#e67e22")
                        self._refresh_server_inventory()
                        self.compare_now()
                        if result.failed:
                            messagebox.showwarning(
                                "Hosted Install Completed with Issues",
                                f"{message}\n\n" + "\n".join(result.failed[:5]),
                            )
                    self.app.dispatch_to_ui(_show)
                except Exception as exc:
                    log.exception("Hosted install failed for %s on %s", selected_path.name, chosen_profile.name)

                    def _show_error() -> None:
                        if not deploy_btn.winfo_exists() or not status.winfo_exists():
                            return
                        deploy_btn.configure(state="normal", text="Install to Hosted Server")
                        status.configure(text=str(exc), text_color="#c0392b")
                        self._status_label.configure(text=str(exc), text_color="#c0392b")
                        messagebox.showerror("Hosted Install Failed", str(exc))

                    self.app.dispatch_to_ui(_show_error)

            threading.Thread(target=_work, daemon=True).start()

        deploy_btn.configure(command=_deploy)
        deploy_btn.pack(side="left", padx=(0, 6))
        ctk.CTkButton(buttons, text="Close", width=100, fg_color="#444444", hover_color="#555555", command=dialog.destroy).pack(side="right")
