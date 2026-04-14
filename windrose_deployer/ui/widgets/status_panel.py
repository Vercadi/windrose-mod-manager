"""Status/log panel widget for displaying operation feedback."""
from __future__ import annotations

import logging
import tkinter as tk
from typing import Optional

import customtkinter as ctk

from ...core.logging_service import LogCapture


class StatusPanel(ctk.CTkFrame):
    """Scrollable log display panel that captures app-wide log output."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._label = ctk.CTkLabel(self, text="Status Log", anchor="w",
                                   font=ctk.CTkFont(weight="bold"))
        self._label.pack(fill="x", padx=8, pady=(4, 0))

        self._textbox = ctk.CTkTextbox(self, height=120, state="disabled",
                                       font=ctk.CTkFont(family="Consolas", size=12))
        self._textbox.pack(fill="both", expand=True, padx=4, pady=4)

        self._capture = LogCapture(callback=self._on_log)
        self._capture.setLevel(logging.INFO)
        logging.getLogger().addHandler(self._capture)

    def _on_log(self, record: logging.LogRecord) -> None:
        fmt = logging.Formatter("%(asctime)s [%(levelname)-5s] %(message)s", datefmt="%H:%M:%S")
        line = fmt.format(record) + "\n"
        try:
            self._textbox.configure(state="normal")
            self._textbox.insert("end", line)
            self._textbox.see("end")
            self._textbox.configure(state="disabled")
        except tk.TclError:
            pass

    def append(self, text: str) -> None:
        """Manually append text to the status panel."""
        try:
            self._textbox.configure(state="normal")
            self._textbox.insert("end", text + "\n")
            self._textbox.see("end")
            self._textbox.configure(state="disabled")
        except tk.TclError:
            pass

    def clear(self) -> None:
        try:
            self._textbox.configure(state="normal")
            self._textbox.delete("1.0", "end")
            self._textbox.configure(state="disabled")
        except tk.TclError:
            pass
