"""Server tab — edit ServerDescription.json safely."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ...models.server_config import ServerConfig

if TYPE_CHECKING:
    from ..app_window import AppWindow

log = logging.getLogger(__name__)


class ServerTab(ctk.CTkFrame):
    def __init__(self, master, app: AppWindow, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._config: Optional[ServerConfig] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_editor()
        self._build_actions()

    def _build_toolbar(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        ctk.CTkLabel(frame, text="Server Configuration",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=8)

        self._load_btn = ctk.CTkButton(frame, text="Load Config", width=120, command=self._on_load)
        self._load_btn.pack(side="right", padx=8)

        self._restore_btn = ctk.CTkButton(frame, text="Restore Backup", width=120,
                                          command=self._on_restore)
        self._restore_btn.pack(side="right", padx=4)

    def _build_editor(self) -> None:
        editor = ctk.CTkScrollableFrame(self)
        editor.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        editor.grid_columnconfigure(1, weight=1)

        self._fields: dict[str, ctk.CTkEntry | ctk.CTkCheckBox] = {}

        fields_spec = [
            ("ServerName", "Server Name", "entry"),
            ("InviteCode", "Invite Code", "entry"),
            ("IsPasswordProtected", "Password Protected", "checkbox"),
            ("Password", "Password", "entry"),
            ("MaxPlayerCount", "Max Players", "entry"),
            ("WorldIslandId", "World Island ID", "entry"),
            ("P2pProxyAddress", "P2P Proxy Address", "entry"),
            ("DeploymentId", "Deployment ID", "entry_readonly"),
            ("PersistentServerId", "Persistent Server ID", "entry_readonly"),
        ]

        for i, (key, label, ftype) in enumerate(fields_spec):
            ctk.CTkLabel(editor, text=label + ":", anchor="w").grid(
                row=i, column=0, sticky="w", padx=(8, 4), pady=6)

            if ftype == "checkbox":
                var = tk.BooleanVar()
                widget = ctk.CTkCheckBox(editor, text="", variable=var)
                widget.grid(row=i, column=1, sticky="w", padx=4, pady=6)
                widget._variable = var
            else:
                var = ctk.StringVar()
                state = "readonly" if ftype == "entry_readonly" else "normal"
                widget = ctk.CTkEntry(editor, textvariable=var, state=state)
                widget.grid(row=i, column=1, sticky="ew", padx=(4, 8), pady=6)
                widget._variable = var

            self._fields[key] = widget

    def _build_actions(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))

        warning = ctk.CTkLabel(
            frame,
            text="⚠  Make sure the Windrose server is shut down before saving changes.",
            text_color="#e67e22",
            font=ctk.CTkFont(size=12),
        )
        warning.pack(side="left", padx=8)

        self._confirm_var = tk.BooleanVar(value=False)
        self._confirm_check = ctk.CTkCheckBox(
            frame, text="I confirm the server is stopped",
            variable=self._confirm_var,
        )
        self._confirm_check.pack(side="left", padx=16)

        self._save_btn = ctk.CTkButton(
            frame, text="Save Config", width=120,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_save,
        )
        self._save_btn.pack(side="right", padx=8)

        self._status_label = ctk.CTkLabel(frame, text="")
        self._status_label.pack(side="right", padx=8)

    # ---------------------------------------------------------- handlers

    def _on_load(self) -> None:
        desc_path = self.app.paths.server_description_json
        if not desc_path or not desc_path.is_file():
            messagebox.showwarning(
                "Not Found",
                "ServerDescription.json not found.\nConfigure the server path in Settings.",
            )
            return

        config = self.app.server_config_svc.load(desc_path)
        if config is None:
            messagebox.showerror("Error", "Failed to load server config.")
            return

        self._config = config
        self._populate_fields(config)
        self._status_label.configure(text="Loaded successfully")
        log.info("Server config loaded")

    def _populate_fields(self, cfg: ServerConfig) -> None:
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

    def _read_fields(self) -> ServerConfig:
        """Read current field values back into a ServerConfig."""
        cfg = self._config or ServerConfig()

        cfg.server_name = self._fields["ServerName"]._variable.get()
        cfg.invite_code = self._fields["InviteCode"]._variable.get()
        cfg.is_password_protected = self._fields["IsPasswordProtected"]._variable.get()
        cfg.password = self._fields["Password"]._variable.get()
        try:
            cfg.max_player_count = int(self._fields["MaxPlayerCount"]._variable.get())
        except ValueError:
            cfg.max_player_count = 0
        cfg.world_island_id = self._fields["WorldIslandId"]._variable.get()
        cfg.p2p_proxy_address = self._fields["P2pProxyAddress"]._variable.get()

        return cfg

    def _on_save(self) -> None:
        if not self._confirm_var.get():
            messagebox.showwarning(
                "Confirmation Required",
                "Please confirm that the server is stopped before saving.",
            )
            return

        desc_path = self.app.paths.server_description_json
        if not desc_path:
            messagebox.showerror("Error", "Server path not configured.")
            return

        config = self._read_fields()
        errors = config.validate()
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return

        success, save_errors = self.app.server_config_svc.save(desc_path, config)
        if success:
            self._status_label.configure(text="Saved successfully")
            self._confirm_var.set(False)
            messagebox.showinfo("Success", "Server configuration saved.\nA backup was created.")
        else:
            messagebox.showerror("Save Failed", "\n".join(save_errors))

    def _on_restore(self) -> None:
        desc_path = self.app.paths.server_description_json
        if not desc_path:
            messagebox.showerror("Error", "Server path not configured.")
            return

        confirm = messagebox.askyesno(
            "Restore Backup",
            "Restore the most recent backup of ServerDescription.json?",
        )
        if not confirm:
            return

        if self.app.server_config_svc.restore_latest(desc_path):
            self._status_label.configure(text="Restored from backup")
            self._on_load()
        else:
            messagebox.showwarning("No Backup", "No server config backups found.")
