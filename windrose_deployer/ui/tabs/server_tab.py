"""Server tab — edit ServerDescription.json and WorldDescription.json."""
from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...models.server_config import ServerConfig
from ...models.world_config import (
    BOOL_PARAM_SPEC,
    COMBAT_DIFFICULTY_OPTIONS,
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
        self._world_path: Optional[Path] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_scrollable_body()
        self._build_actions()

    # ================================================================== layout

    def _build_toolbar(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        ctk.CTkLabel(frame, text="Server & World Configuration",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=8)

        self._load_btn = ctk.CTkButton(frame, text="Load All", width=100, command=self._on_load_all)
        self._load_btn.pack(side="right", padx=8)

        self._restore_btn = ctk.CTkButton(frame, text="Restore Backup", width=120,
                                          command=self._on_restore_server)
        self._restore_btn.pack(side="right", padx=4)

    def _build_scrollable_body(self) -> None:
        self._body = ctk.CTkScrollableFrame(self)
        self._body.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self._body.grid_columnconfigure(0, weight=1)

        self._build_server_section(self._body)
        self._build_world_section(self._body)

        # Scroll hint — placed over the bottom of the scrollable area
        self._scroll_hint = ctk.CTkLabel(
            self,
            text="\u25BC  Scroll down for World Settings  \u25BC",
            text_color="#888888",
            font=ctk.CTkFont(size=11),
            fg_color=("gray86", "gray17"),
            corner_radius=8,
            height=24,
            width=260,
        )
        self._scroll_hint.place(relx=0.5, rely=0.93, anchor="center")

        # Poll scroll position to auto-hide the hint
        self._poll_scroll_hint()

    def _poll_scroll_hint(self) -> None:
        """Periodically check scroll position and hide hint when near bottom."""
        try:
            canvas = self._body._parent_canvas
            _, bottom = canvas.yview()
            if bottom >= 0.6:
                self._scroll_hint.place_forget()
            else:
                if not self._scroll_hint.winfo_ismapped():
                    self._scroll_hint.place(relx=0.5, rely=0.93, anchor="center")
        except Exception:
            pass
        self.after(300, self._poll_scroll_hint)

    # ---- Server Description section ----

    def _build_server_section(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        ctk.CTkLabel(header, text="Server Description",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

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
            ctk.CTkLabel(editor, text=label + ":", anchor="w").grid(
                row=i, column=0, sticky="w", padx=(8, 4), pady=5)

            if ftype == "checkbox":
                var = tk.BooleanVar()
                widget = ctk.CTkCheckBox(editor, text="", variable=var)
                widget.grid(row=i, column=1, sticky="w", padx=4, pady=5)
                widget._variable = var
            else:
                var = ctk.StringVar()
                state = "readonly" if ftype == "entry_readonly" else "normal"
                widget = ctk.CTkEntry(editor, textvariable=var, state=state)
                widget.grid(row=i, column=1, sticky="ew", padx=(4, 8), pady=5)
                widget._variable = var

            self._fields[key] = widget

        save_row = len(fields_spec)
        self._server_save_btn = ctk.CTkButton(
            editor, text="Save Server Config", width=160,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_save_server,
        )
        self._server_save_btn.grid(row=save_row, column=1, sticky="w", padx=4, pady=(8, 4))

    # ---- World Description section ----

    def _build_world_section(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=2, column=0, sticky="ew", pady=(8, 2))
        ctk.CTkLabel(header, text="World Settings",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        self._world_info_label = ctk.CTkLabel(header, text="(not loaded)", text_color="#95a5a6")
        self._world_info_label.pack(side="left", padx=8)

        editor = ctk.CTkFrame(parent)
        editor.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        editor.grid_columnconfigure(1, weight=1)

        self._world_fields: dict[str, any] = {}
        row = 0

        # World Name
        ctk.CTkLabel(editor, text="World Name:", anchor="w").grid(
            row=row, column=0, sticky="w", padx=(8, 4), pady=5)
        var = ctk.StringVar()
        w = ctk.CTkEntry(editor, textvariable=var, state="readonly")
        w.grid(row=row, column=1, sticky="ew", padx=(4, 8), pady=5)
        w._variable = var
        self._world_fields["WorldName"] = w
        row += 1

        # Preset
        ctk.CTkLabel(editor, text="Preset:", anchor="w").grid(
            row=row, column=0, sticky="w", padx=(8, 4), pady=5)
        self._preset_var = ctk.StringVar(value="Medium")
        preset_menu = ctk.CTkOptionMenu(editor, variable=self._preset_var,
                                        values=PRESET_OPTIONS, width=140,
                                        command=self._on_preset_change)
        preset_menu.grid(row=row, column=1, sticky="w", padx=4, pady=5)
        row += 1

        # Combat Difficulty
        ctk.CTkLabel(editor, text="Combat Difficulty:", anchor="w").grid(
            row=row, column=0, sticky="w", padx=(8, 4), pady=5)
        self._combat_diff_var = ctk.StringVar(value="Normal")
        cd_menu = ctk.CTkOptionMenu(editor, variable=self._combat_diff_var,
                                    values=list(_CD_DISPLAY.values()), width=140)
        cd_menu.grid(row=row, column=1, sticky="w", padx=4, pady=5)
        row += 1

        # Separator
        sep = ctk.CTkFrame(editor, height=2, fg_color="#444444")
        sep.grid(row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        row += 1

        # Bool params
        for tag_key, (display_name, default) in BOOL_PARAM_SPEC.items():
            ctk.CTkLabel(editor, text=display_name + ":", anchor="w").grid(
                row=row, column=0, sticky="w", padx=(8, 4), pady=5)
            var = tk.BooleanVar(value=default)
            cb = ctk.CTkCheckBox(editor, text="", variable=var)
            cb.grid(row=row, column=1, sticky="w", padx=4, pady=5)
            cb._variable = var
            self._world_fields[f"bool_{tag_key}"] = cb
            row += 1

        # Another separator
        sep2 = ctk.CTkFrame(editor, height=2, fg_color="#444444")
        sep2.grid(row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        row += 1

        # Float params with sliders
        for tag_key, (display_name, default, lo, hi) in FLOAT_PARAM_SPEC.items():
            ctk.CTkLabel(editor, text=display_name + ":", anchor="w").grid(
                row=row, column=0, sticky="w", padx=(8, 4), pady=5)

            slider_frame = ctk.CTkFrame(editor, fg_color="transparent")
            slider_frame.grid(row=row, column=1, sticky="ew", padx=(4, 8), pady=5)
            slider_frame.grid_columnconfigure(0, weight=1)

            value_var = ctk.StringVar(value=f"{default:.2f}")
            value_label = ctk.CTkLabel(slider_frame, textvariable=value_var, width=50)
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
            row += 1

        # Save world button
        self._world_save_btn = ctk.CTkButton(
            editor, text="Save World Settings", width=160,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_save_world,
        )
        self._world_save_btn.grid(row=row, column=1, sticky="w", padx=4, pady=(8, 4))

    # ---- Actions bar ----

    def _build_actions(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))

        warning = ctk.CTkLabel(
            frame,
            text="Make sure the Windrose server is shut down before saving any changes.",
            text_color="#e67e22",
            font=ctk.CTkFont(size=12),
        )
        warning.pack(side="left", padx=8)

        self._confirm_var = tk.BooleanVar(value=False)
        self._confirm_check = ctk.CTkCheckBox(
            frame, text="Server is stopped",
            variable=self._confirm_var,
        )
        self._confirm_check.pack(side="left", padx=16)

        self._status_label = ctk.CTkLabel(frame, text="")
        self._status_label.pack(side="right", padx=8)

    # ================================================================== Server handlers

    def _on_load_all(self) -> None:
        self._load_server_config()
        self._load_world_config()

    def _load_server_config(self) -> None:
        desc_path = self.app.paths.server_description_json
        if not desc_path or not desc_path.is_file():
            messagebox.showwarning(
                "Not Found",
                "ServerDescription.json not found.\nConfigure the client path in Settings.",
            )
            return

        config = self.app.server_config_svc.load(desc_path)
        if config is None:
            messagebox.showerror("Error", "Failed to load server config.")
            return

        self._config = config
        self._populate_server_fields(config)
        self._status_label.configure(text="Server config loaded")
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

    def _on_save_server(self) -> None:
        if not self._confirm_var.get():
            messagebox.showwarning("Confirmation Required",
                                   "Please confirm that the server is stopped before saving.")
            return

        desc_path = self.app.paths.server_description_json
        if not desc_path:
            messagebox.showerror("Error", "Client path not configured.")
            return

        config = self._read_server_fields()
        errors = config.validate()
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return

        success, save_errors = self.app.server_config_svc.save(desc_path, config)
        if success:
            self._status_label.configure(text="Server config saved")
            self._confirm_var.set(False)
            messagebox.showinfo("Success", "Server configuration saved.\nA backup was created.")
        else:
            messagebox.showerror("Save Failed", "\n".join(save_errors))

    def _on_restore_server(self) -> None:
        desc_path = self.app.paths.server_description_json
        if not desc_path:
            messagebox.showerror("Error", "Client path not configured.")
            return

        confirm = messagebox.askyesno(
            "Restore Backup",
            "Restore the most recent server/world config backup?",
        )
        if not confirm:
            return

        if self.app.server_config_svc.restore_latest(desc_path):
            self._status_label.configure(text="Restored from backup")
            self._on_load_all()
        else:
            messagebox.showwarning("No Backup", "No server config backups found.")

    # ================================================================== World handlers

    def _load_world_config(self) -> None:
        if not self._config:
            self._world_info_label.configure(text="(load server config first)")
            return

        island_id = self._config.world_island_id
        if not island_id:
            self._world_info_label.configure(text="(no WorldIslandId set)")
            return

        world_path = self.app.world_config_svc.find_world_by_island_id(
            island_id, self.app.paths.local_save_root,
        )
        if world_path is None:
            self._world_info_label.configure(text=f"(world {island_id[:8]}... not found)")
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
        log.info("World config loaded: %s", config.world_name)

    def _populate_world_fields(self, cfg: WorldConfig) -> None:
        # World name (read-only display)
        w = self._world_fields["WorldName"]
        w.configure(state="normal")
        w._variable.set(cfg.world_name)
        w.configure(state="readonly")

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

    def _read_world_fields(self) -> WorldConfig:
        cfg = self._world_config or WorldConfig()

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

    def _on_save_world(self) -> None:
        if not self._confirm_var.get():
            messagebox.showwarning("Confirmation Required",
                                   "Please confirm that the server is stopped before saving.")
            return

        if not self._world_path:
            messagebox.showerror("Error", "No world loaded. Click 'Load All' first.")
            return

        config = self._read_world_fields()
        errors = config.validate()
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return

        success, save_errors = self.app.world_config_svc.save(self._world_path, config)
        if success:
            self._status_label.configure(text="World settings saved")
            self._confirm_var.set(False)
            messagebox.showinfo("Success",
                                f"World settings for \"{config.world_name}\" saved.\n"
                                "A backup was created.")
        else:
            messagebox.showerror("Save Failed", "\n".join(save_errors))
