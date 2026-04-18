"""Server tab — edit ServerDescription.json and WorldDescription.json."""
from __future__ import annotations

import logging
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
from ...core.remote_deployer import plan_remote_deployment
from ...models.deployment_record import DeploymentRecord
from ...models.mod_install import expand_target_values
from ...models.remote_profile import RemoteProfile
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
    def __init__(self, master, app: AppWindow, **kwargs):
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

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_scrollable_body()
        self._build_actions()
        self.refresh_remote_profiles()
        self._on_source_changed("dedicated_server")

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
        )

        hosted_setup_btn = ctk.CTkButton(
            frame,
            text="Hosted Setup",
            width=112,
            height=self.app.ui_tokens.compact_button_height,
            font=self.app.ui_font("body"),
            fg_color="#555555",
            hover_color="#666666",
            command=self.open_hosted_setup,
        )
        hosted_setup_btn.pack(side="right", padx=4)
        self._action_buttons.append(hosted_setup_btn)
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

        source_card = ctk.CTkFrame(frame)
        source_card.grid(row=0, column=0, sticky="ew", pady=(0, 6))
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
        inventory_card.grid(row=1, column=0, sticky="ew", pady=(0, 6))
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
        sync_card.grid(row=2, column=0, sticky="ew", pady=(0, 6))
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
        apply_card.grid(row=3, column=0, sticky="ew", pady=(0, 6))
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
        recovery_card.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        recovery_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(recovery_card, text="Recovery Shortcut", font=self.app.ui_font("card_title")).grid(
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
            text="Open Recovery Center",
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
        self._update_source_summary()

    def _on_source_changed(self, value: str) -> None:
        self._source_value = value
        self._source_var.set(value)
        is_hosted = value == "hosted"
        if is_hosted:
            if not self._remote_profile_label.winfo_manager():
                self._remote_profile_label.pack(side="left", padx=(0, 4))
            if not self._remote_profile_menu.winfo_manager():
                self._remote_profile_menu.pack(side="left")
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
            self._test_btn.configure(state="disabled")
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
        self._refresh_server_inventory()
        self._update_sync_placeholder(force=True)

    def _on_source_segment_changed(self, value: str) -> None:
        source = value.strip().lower().replace(" ", "_")
        mapped = {
            "local_server": "server",
            "dedicated_server": "dedicated_server",
            "hosted_server": "hosted",
        }.get(source, source)
        self._on_source_changed(mapped)

    def refresh_view(self) -> None:
        self.refresh_remote_profiles()
        self._update_source_summary()
        self._update_apply_summary()
        self._refresh_server_inventory()
        self._update_sync_placeholder()

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

    def _update_source_summary(self) -> None:
        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                text = "Mode: Hosted Server\nProfile: (not selected)\nServer Folder: (not set)"
            else:
                text = (
                    f"Mode: Hosted Server\n"
                    f"Profile: {profile.name}\n"
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
            if profile and profile.restart_command:
                lines.append("Restart: hosted command is configured.")
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
                except Exception as exc:
                    text = f"Could not load hosted mod inventory:\n{exc}"

                def _show() -> None:
                    self._inventory_btn.configure(state="normal", text="Refresh Server Mods")
                    self._set_status_box(self._inventory_box, text)

                self.after(0, _show)

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
        self._set_status_box(self._inventory_box, self._local_server_inventory_text(server_mods, label, snapshot))

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
            log.info("Hosted connection result for %s: %s", profile.name, message)

            def _show() -> None:
                self._test_btn.configure(state="normal", text="Test Connection")
                self._status_label.configure(text=message, text_color="#2d8a4e" if ok else "#c0392b")

            self.after(0, _show)

        threading.Thread(target=_work, daemon=True).start()

    def compare_now(self) -> None:
        if self._source_var.get() == "hosted":
            profile = self._selected_remote_profile()
            if profile is None:
                self._set_status_box(self._sync_box, "Choose a hosted profile first.")
                return
            self._set_status_box(self._sync_box, "Comparing client mods with hosted server files...")

            def _work() -> None:
                try:
                    remote_files = self.app.remote_deployer.list_remote_files(profile)
                    report = self.app.server_sync.compare_hosted(self.app.manifest.list_mods(), remote_files)
                    text = self._sync_report_text(report)
                except Exception as exc:
                    text = f"Hosted comparison failed:\n{exc}"
                self.after(0, lambda: self._set_status_box(self._sync_box, text))

            threading.Thread(target=_work, daemon=True).start()
            return

        report = self.app.server_sync.compare_local(self.app.manifest.list_mods(), target=self._active_local_target())
        self._set_status_box(self._sync_box, self._sync_report_text(report))

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
            self.after(0, lambda: self._finish_remote_load(profile.name, config, world_config, world_path))

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
            messagebox.showerror(
                "Hosted Load Failed",
                "Failed to load hosted server settings.\n"
                "Check the profile connection details, server folder, and overrides.",
            )
            return

        self._config = config
        self._populate_server_fields(config)
        self._status_label.configure(text=f"Hosted server settings loaded from {profile_name}", text_color="#2d8a4e")

        if config.world_island_id:
            if world_config is not None and world_path is not None:
                self._world_config = world_config
                self._world_path = world_path
                self._populate_world_fields(world_config)
                self._world_info_label.configure(
                    text=f'"{world_config.world_name}" — {world_config.world_preset_type}',
                    text_color="#2d8a4e",
                )
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
        self.app.refresh_backups_tab()

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
                "server settings file, and world saves folder from it. If your SFTP login already opens inside "
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
        ctk.CTkLabel(connection, text="Host:").grid(row=2, column=0, sticky="w", padx=12, pady=4)
        ctk.CTkEntry(connection, textvariable=vars_map["host"]).grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(connection, text="Port:").grid(row=2, column=2, sticky="w", padx=(8, 4), pady=4)
        ctk.CTkEntry(connection, textvariable=vars_map["port"], width=86).grid(row=2, column=3, sticky="e", padx=(0, 12), pady=4)
        ctk.CTkLabel(
            connection,
            text="Host = your SSH/SFTP hostname or LAN IP. Port = the SSH/SFTP port, usually 22.",
            justify="left",
            wraplength=310,
            text_color="#95a5a6",
        ).grid(row=3, column=1, columnspan=3, sticky="ew", padx=8, pady=(0, 4))
        ctk.CTkEntry(connection, textvariable=vars_map["username"]).grid(
            row=4, column=1, columnspan=3, sticky="ew", padx=8, pady=4
        )
        ctk.CTkLabel(connection, text="Username:").grid(row=4, column=0, sticky="w", padx=12, pady=4)
        ctk.CTkLabel(connection, text="Auth Mode:").grid(row=5, column=0, sticky="w", padx=12, pady=4)
        auth_menu = ctk.CTkOptionMenu(connection, variable=auth_var, values=["password", "key"], width=120)
        auth_menu.grid(row=5, column=1, sticky="w", padx=8, pady=4)
        ctk.CTkLabel(
            connection,
            text="Use password for hosting-panel accounts or a private key for OpenSSH/SFTP logins.",
            justify="left",
            wraplength=310,
            text_color="#95a5a6",
        ).grid(row=5, column=2, columnspan=2, sticky="ew", padx=(8, 12), pady=4)
        ctk.CTkLabel(connection, text="Password:").grid(row=6, column=0, sticky="w", padx=12, pady=4)
        password_entry = ctk.CTkEntry(connection, textvariable=vars_map["password"], show="*")
        password_entry.grid(row=6, column=1, columnspan=3, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(connection, text="Private Key:").grid(row=7, column=0, sticky="w", padx=12, pady=4)
        key_row = ctk.CTkFrame(connection, fg_color="transparent")
        key_row.grid(row=7, column=1, columnspan=3, sticky="ew", padx=8, pady=4)
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
            ("Restart Command", "restart"),
        ]
        for row, (label, key) in enumerate(advanced_fields, start=2):
            ctk.CTkLabel(overrides, text=label + ":").grid(row=row, column=0, sticky="w", padx=12, pady=4)
            ctk.CTkEntry(overrides, textvariable=vars_map[key]).grid(row=row, column=1, sticky="ew", padx=8, pady=4)

        status = ctk.CTkLabel(body, text="", text_color="#95a5a6", justify="left", wraplength=520)
        status.grid(row=5, column=0, sticky="ew", padx=8, pady=(4, 8))

        def _build_profile() -> RemoteProfile:
            profile = RemoteProfile(
                profile_id=current.profile_id,
                name=vars_map["name"].get().strip() or "Hosted Server",
                host=vars_map["host"].get().strip(),
                port=int(vars_map["port"].get().strip() or 22),
                username=vars_map["username"].get().strip(),
                auth_mode=auth_var.get(),
                password=vars_map["password"].get(),
                private_key_path=vars_map["key"].get().strip(),
                remote_root_dir=vars_map["root"].get().strip(),
                remote_mods_dir=vars_map["mods"].get().strip(),
                remote_server_description_path=vars_map["server_desc"].get().strip(),
                remote_save_root=vars_map["save_root"].get().strip(),
                restart_command=vars_map["restart"].get().strip(),
            )
            profile.apply_root_defaults(overwrite=False)
            return profile

        def _apply_root_defaults(overwrite: bool = True) -> None:
            try:
                profile = _build_profile()
            except ValueError:
                messagebox.showerror("Invalid Port", "Port must be a whole number.")
                return
            if not profile.remote_root_dir.strip():
                status.configure(text="Enter the hosted server folder first.", text_color="#c0392b")
                return
            profile.apply_root_defaults(overwrite=overwrite)
            vars_map["root"].set(profile.remote_root_dir)
            vars_map["mods"].set(profile.remote_mods_dir)
            vars_map["server_desc"].set(profile.remote_server_description_path)
            vars_map["save_root"].set(profile.remote_save_root)
            status.configure(
                text="Derived Windrose hosted paths from the server folder. Review them before saving.",
                text_color="#2d8a4e",
            )

        def _sync_auth_fields(*_args) -> None:
            is_key = auth_var.get() == "key"
            password_entry.configure(state="disabled" if is_key else "normal")
            key_entry.configure(state="normal" if is_key else "disabled")
            key_browse_btn.configure(state="normal" if is_key else "disabled")

        def _save() -> None:
            try:
                profile = _build_profile()
            except ValueError:
                messagebox.showerror("Invalid Port", "Port must be a whole number.")
                return
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
                messagebox.showerror("Invalid Port", "Port must be a whole number.")
                return
            status.configure(text="Testing hosted connection...", text_color="#95a5a6")

            def _work() -> None:
                ok, message = self.app.remote_deployer.test_connection(profile)
                self.after(0, lambda: status.configure(text=message, text_color="#2d8a4e" if ok else "#c0392b"))

            threading.Thread(target=_work, daemon=True).start()

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.grid(row=6, column=0, sticky="ew", padx=8, pady=(4, 8))
        ctk.CTkButton(
            buttons,
            text="Auto-Detect Paths",
            width=146,
            fg_color="#555555",
            hover_color="#666666",
            command=_apply_root_defaults,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(buttons, text="Test Connection", width=120, command=_test).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Save Profile", width=110, fg_color="#2d8a4e", hover_color="#236b3d", command=_save).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Close", width=100, fg_color="#444444", hover_color="#555555", command=dialog.destroy).pack(side="right")
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
        preview.insert("1.0", f"Archive: {selected_path.name}\nType: {info.archive_type.value}\nFiles: {info.total_files}\n")
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
                    self._record_action(
                        action="hosted_upload",
                        target="hosted",
                        notes=f"Uploaded {selected_path.name} to hosted server {chosen_profile.name} ({result.summary})",
                    )
                    message = result.summary
                    def _show() -> None:
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
                    self.after(0, _show)
                except Exception as exc:
                    log.exception("Hosted install failed for %s on %s", selected_path.name, chosen_profile.name)

                    def _show_error() -> None:
                        deploy_btn.configure(state="normal", text="Install to Hosted Server")
                        status.configure(text=str(exc), text_color="#c0392b")
                        self._status_label.configure(text=str(exc), text_color="#c0392b")
                        messagebox.showerror("Hosted Install Failed", str(exc))

                    self.after(0, _show_error)

            threading.Thread(target=_work, daemon=True).start()

        deploy_btn.configure(command=_deploy)
        deploy_btn.pack(side="left", padx=(0, 6))
        ctk.CTkButton(buttons, text="Close", width=100, fg_color="#444444", hover_color="#555555", command=dialog.destroy).pack(side="right")
