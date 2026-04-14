"""About tab — app info, author, and links."""
from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

import customtkinter as ctk

from ... import __app_name__, __version__

if TYPE_CHECKING:
    from ..app_window import AppWindow

NEXUS_URL = "https://www.nexusmods.com/windrose/mods/29"
GITHUB_URL = "https://github.com/Vercadi/windrose-mod-manager"


class AboutTab(ctk.CTkFrame):
    def __init__(self, master, app: "AppWindow", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.4, anchor="center")

        ctk.CTkLabel(
            container,
            text=__app_name__,
            font=ctk.CTkFont(size=28, weight="bold"),
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            container,
            text=f"Version {__version__}",
            font=ctk.CTkFont(size=16),
            text_color="#aaaaaa",
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            container,
            text="by Vercadi",
            font=ctk.CTkFont(size=14),
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            container,
            text="MIT License",
            font=ctk.CTkFont(size=12),
            text_color="#95a5a6",
        ).pack(pady=(0, 20))

        links = ctk.CTkFrame(container, fg_color="transparent")
        links.pack(pady=(0, 20))

        ctk.CTkButton(
            links, text="Nexus Mods Page", width=160,
            fg_color="#d98f40", hover_color="#b87530",
            command=lambda: webbrowser.open(NEXUS_URL),
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            links, text="GitHub Repository", width=160,
            fg_color="#555555", hover_color="#666666",
            command=lambda: webbrowser.open(GITHUB_URL),
        ).pack(side="left", padx=8)

        ctk.CTkLabel(
            container,
            text=(
                "A mod manager for Windrose — install, manage, and back up\n"
                "mods for the client game and dedicated server."
            ),
            font=ctk.CTkFont(size=12),
            text_color="#888888",
            justify="center",
        ).pack(pady=(0, 0))
