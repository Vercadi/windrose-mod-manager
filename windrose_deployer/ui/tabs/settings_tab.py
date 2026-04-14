"""Settings tab — configure paths and preferences."""
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
    def __init__(self, master, app: AppWindow, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)

        self._build_paths_section()
        self._build_actions_section()
        self._build_info_section()
        self._populate()

    def _build_paths_section(self) -> None:
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Paths", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 4))

        self._path_vars: dict[str, ctk.StringVar] = {}
        self._status_labels: dict[str, ctk.CTkLabel] = {}

        paths_spec = [
            ("client_root", "Client Root"),
            ("server_root", "Server Root"),
            ("local_config", "Local Config"),
            ("local_save_root", "Local Save Root"),
            ("backup_dir", "Backup Directory"),
        ]

        for i, (key, label) in enumerate(paths_spec, start=1):
            ctk.CTkLabel(frame, text=label + ":").grid(row=i, column=0, sticky="w", padx=8, pady=4)

            var = ctk.StringVar()
            self._path_vars[key] = var
            entry = ctk.CTkEntry(frame, textvariable=var)
            entry.grid(row=i, column=1, sticky="ew", padx=4, pady=4)

            btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
            btn_frame.grid(row=i, column=2, padx=4, pady=4)

            browse_btn = ctk.CTkButton(
                btn_frame, text="Browse", width=70,
                command=lambda k=key: self._browse_path(k),
            )
            browse_btn.pack(side="left", padx=(0, 4))

            open_btn = ctk.CTkButton(
                btn_frame, text="Open", width=50,
                fg_color="#555555", hover_color="#666666",
                command=lambda k=key: self._open_path(k),
            )
            open_btn.pack(side="left")

            status = ctk.CTkLabel(frame, text="—", width=60)
            status.grid(row=i, column=3, padx=(4, 8), pady=4)
            self._status_labels[key] = status

    def _build_actions_section(self) -> None:
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=1, column=0, sticky="ew", padx=8, pady=4)

        self._autodetect_btn = ctk.CTkButton(
            frame, text="Auto-Detect All Paths", width=180,
            command=self._on_autodetect,
        )
        self._autodetect_btn.pack(side="left", padx=8)

        self._validate_btn = ctk.CTkButton(
            frame, text="Validate Paths", width=140,
            command=self._on_validate,
        )
        self._validate_btn.pack(side="left", padx=8)

        self._save_btn = ctk.CTkButton(
            frame, text="Save Settings", width=140,
            fg_color="#2d8a4e", hover_color="#236b3d",
            command=self._on_save,
        )
        self._save_btn.pack(side="left", padx=8)

        self._open_data_btn = ctk.CTkButton(
            frame, text="Open Deployer Data", width=170,
            fg_color="#555555", hover_color="#666666",
            command=self._on_open_data_folder,
        )
        self._open_data_btn.pack(side="right", padx=8)

    def _build_info_section(self) -> None:
        self._info_box = ctk.CTkTextbox(self, height=120, state="disabled",
                                        font=ctk.CTkFont(family="Consolas", size=11))
        self._info_box.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 4))
        self.grid_rowconfigure(2, weight=1)

    # ---------------------------------------------------------- populate

    def _populate(self) -> None:
        paths = self.app.paths
        if paths.client_root:
            self._path_vars["client_root"].set(str(paths.client_root))
        if paths.server_root:
            self._path_vars["server_root"].set(str(paths.server_root))
        if paths.local_config:
            self._path_vars["local_config"].set(str(paths.local_config))
        if paths.local_save_root:
            self._path_vars["local_save_root"].set(str(paths.local_save_root))
        if paths.backup_dir:
            self._path_vars["backup_dir"].set(str(paths.backup_dir))
        self._on_validate()

    # ---------------------------------------------------------- handlers

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
        if detected.local_config:
            self._path_vars["local_config"].set(str(detected.local_config))
        if detected.local_save_root:
            self._path_vars["local_save_root"].set(str(detected.local_save_root))

        self._on_validate()
        self._info_append("Auto-detection complete.")
        log.info("Auto-detection finished")

    def _on_validate(self) -> None:
        validators = {
            "client_root": validate_client_root,
            "server_root": validate_server_root,
            "local_config": validate_local_config,
        }

        for key, var in self._path_vars.items():
            path_str = var.get().strip()
            label = self._status_labels[key]

            if not path_str:
                label.configure(text="—", text_color="#95a5a6")
                continue

            path = Path(path_str)

            if key in validators:
                valid, msg = validators[key](path)
                if valid:
                    label.configure(text="OK", text_color="#2d8a4e")
                else:
                    label.configure(text="FAIL", text_color="#c0392b")
            elif key == "local_save_root":
                if path.is_dir():
                    label.configure(text="OK", text_color="#2d8a4e")
                else:
                    label.configure(text="FAIL", text_color="#c0392b")
            elif key == "backup_dir":
                if path.is_dir() or path.parent.is_dir():
                    label.configure(text="OK", text_color="#2d8a4e")
                else:
                    label.configure(text="FAIL", text_color="#c0392b")

    def _on_save(self) -> None:
        paths = self.app.paths

        for key, var in self._path_vars.items():
            val = var.get().strip()
            p = Path(val) if val else None
            setattr(paths, key, p)

        self.app.save_settings()
        self._info_append("Settings saved.")
        self._on_validate()
        messagebox.showinfo("Saved", "Settings saved successfully.")
        log.info("Settings saved")

    def _open_path(self, key: str) -> None:
        """Open the folder for a given path setting in the system file explorer."""
        path_str = self._path_vars[key].get().strip()
        if not path_str:
            messagebox.showinfo("Not Set", f"{key.replace('_', ' ').title()} is not configured.")
            return
        p = Path(path_str)
        if p.is_dir():
            os.startfile(str(p))
        elif p.is_file():
            os.startfile(str(p.parent))
        else:
            messagebox.showinfo("Not Found", f"Path does not exist:\n{p}")

    def _on_open_data_folder(self) -> None:
        from ..app_window import DEFAULT_DATA_DIR
        if DEFAULT_DATA_DIR.is_dir():
            os.startfile(str(DEFAULT_DATA_DIR))
        else:
            messagebox.showinfo("Not Found", f"Data folder not found:\n{DEFAULT_DATA_DIR}")

    def _info_append(self, text: str) -> None:
        try:
            self._info_box.configure(state="normal")
            self._info_box.insert("end", text + "\n")
            self._info_box.see("end")
            self._info_box.configure(state="disabled")
        except Exception:
            pass
