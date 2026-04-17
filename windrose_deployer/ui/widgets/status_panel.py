"""Status/log panel widget for displaying operation feedback."""
from __future__ import annotations

import logging
import tkinter as tk
from typing import Optional

import customtkinter as ctk

from ...core.logging_service import LogCapture


class StatusPanel(ctk.CTkFrame):
    """Scrollable log display panel that captures app-wide log output."""

    def __init__(self, master, *, toggle_callback=None, collapsed: bool = False, **kwargs):
        super().__init__(master, **kwargs)
        self._toggle_callback = toggle_callback
        self._collapsed = False

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=4, pady=(4, 0))

        self._label = ctk.CTkLabel(header, text="Technical Log", anchor="w",
                                   font=ctk.CTkFont(weight="bold"))
        self._label.pack(side="left", padx=8, pady=(0, 2))

        self._clear_btn = ctk.CTkButton(
            header, text="Clear", width=60,
            fg_color="#555555", hover_color="#666666",
            command=self.clear,
        )
        self._clear_btn.pack(side="right", padx=(4, 4))

        self._toggle_btn = ctk.CTkButton(
            header, text="Hide", width=70,
            fg_color="#555555", hover_color="#666666",
            command=self.toggle_collapsed,
        )
        self._toggle_btn.pack(side="right", padx=(0, 4))

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True)

        self._textbox = ctk.CTkTextbox(self._body, height=120, state="disabled",
                                       font=ctk.CTkFont(family="Consolas", size=12))
        self._textbox.pack(fill="both", expand=True, padx=4, pady=4)

        self._capture = LogCapture(callback=self._on_log)
        self._capture.setLevel(logging.INFO)
        logging.getLogger().addHandler(self._capture)
        self.set_collapsed(collapsed)

    def apply_ui_preferences(self, app) -> None:
        self._label.configure(font=app.ui_font("card_title"))
        self._clear_btn.configure(
            font=app.ui_font("body"),
            height=app.ui_tokens.compact_button_height,
        )
        self._toggle_btn.configure(
            font=app.ui_font("body"),
            height=app.ui_tokens.compact_button_height,
        )
        self._textbox.configure(font=app.ui_font("mono"))

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

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        if collapsed:
            self._body.pack_forget()
            self._toggle_btn.configure(text="Show")
        else:
            if not self._body.winfo_manager():
                self._body.pack(fill="both", expand=True)
            self._toggle_btn.configure(text="Hide")
        if self._toggle_callback is not None:
            try:
                self._toggle_callback(collapsed)
            except Exception:
                pass

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed
