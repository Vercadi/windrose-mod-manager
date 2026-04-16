"""Help / About screen for support, trust, and update actions."""
from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

from ... import __app_name__, __version__

if TYPE_CHECKING:
    from ..app_window import AppWindow

NEXUS_URL = "https://www.nexusmods.com/windrose/mods/29"
GITHUB_URL = "https://github.com/Vercadi/windrose-mod-manager"
KOFI_URL = "https://ko-fi.com/vercadi"
PATREON_URL = "https://www.patreon.com/cw/Vercadi"


class AboutTab(ctk.CTkFrame):
    def __init__(self, master, app: "AppWindow", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._body = ctk.CTkScrollableFrame(self)
        self._body.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self._body.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_support_section()
        self._build_updates_section()
        self._build_troubleshooting_section()

    def _build_header(self) -> None:
        card = ctk.CTkFrame(self._body)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Help / About",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))

        self._version_label = ctk.CTkLabel(
            card,
            text=f"{__app_name__} v{__version__}",
            text_color="#95a5a6",
            font=ctk.CTkFont(size=13),
        )
        self._version_label.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))

        ctk.CTkLabel(
            card,
            text=(
                "Windrose Mod Manager is focused on safe client and server modding: "
                "import archives, verify what is applied, manage hosted servers, and recover cleanly."
            ),
            justify="left",
            wraplength=760,
            text_color="#c1c7cd",
        ).grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))

    def _build_support_section(self) -> None:
        card = ctk.CTkFrame(self._body)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Support and Links",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 10))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        ctk.CTkButton(
            actions,
            text="Open Nexus Page",
            width=150,
            fg_color="#d98f40",
            hover_color="#b87530",
            command=lambda: webbrowser.open(NEXUS_URL),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            actions,
            text="Open GitHub",
            width=140,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: webbrowser.open(GITHUB_URL),
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            actions,
            text="Open Backup Storage",
            width=160,
            command=self._open_backup_storage,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            actions,
            text="Open Technical Log Folder",
            width=180,
            fg_color="#555555",
            hover_color="#666666",
            command=self._open_data_folder,
        ).pack(side="left", padx=8)

        ctk.CTkLabel(
            card,
            text="Support development",
            text_color="#c1c7cd",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 6))

        donate_actions = ctk.CTkFrame(card, fg_color="transparent")
        donate_actions.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 8))

        ctk.CTkButton(
            donate_actions,
            text="Support on Ko-fi",
            width=140,
            fg_color="#1f8bff",
            hover_color="#166fcc",
            command=lambda: webbrowser.open(KOFI_URL),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            donate_actions,
            text="Support on Patreon",
            width=150,
            fg_color="#f96854",
            hover_color="#d85745",
            command=lambda: webbrowser.open(PATREON_URL),
        ).pack(side="left", padx=8)

        self._support_hint = ctk.CTkLabel(
            card,
            text=(
                "Use Nexus for release notes and downloads. Use GitHub when you want to report an issue, "
                "track roadmap work, or inspect technical changes. If you want to support continued work on the "
                "manager, Ko-fi and Patreon are available here as well."
            ),
            justify="left",
            wraplength=760,
            text_color="#95a5a6",
        )
        self._support_hint.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 14))

    def _build_updates_section(self) -> None:
        card = ctk.CTkFrame(self._body)
        card.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text="Updates",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 10))

        self._update_btn = ctk.CTkButton(
            card,
            text="Check for Updates",
            width=160,
            fg_color="#2980b9",
            hover_color="#2471a3",
            command=self._on_check_update,
        )
        self._update_btn.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        self._update_status = ctk.CTkLabel(
            card,
            text="The app will also show a banner when a new GitHub release is found.",
            justify="left",
            wraplength=560,
            text_color="#95a5a6",
        )
        self._update_status.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(0, 8))

        self._release_hint = ctk.CTkLabel(
            card,
            text=(
                "Update flow: GitHub releases are checked in-app, but you stay in control of when to download "
                "and replace the executable."
            ),
            justify="left",
            wraplength=760,
            text_color="#95a5a6",
        )
        self._release_hint.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))

    def _build_troubleshooting_section(self) -> None:
        card = ctk.CTkFrame(self._body)
        card.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Troubleshooting",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 10))

        text = ctk.CTkTextbox(
            card,
            height=180,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        text.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        text.insert(
            "1.0",
            "\n".join(
                [
                    "Start in Mods to inspect an archive before installing it.",
                    "Use Server to compare local or hosted server state before applying changes.",
                    "Use Recovery to undo installs or restore previous config versions.",
                    "If hosted connection tests fail, verify the SSH account, auth mode, and server folder.",
                    "If installs look wrong, compare with the Technical Log before rebuilding the executable.",
                ]
            ),
        )
        text.configure(state="disabled")

    def refresh_view(self) -> None:
        self._version_label.configure(text=f"{__app_name__} v{__version__}")

    def _on_check_update(self) -> None:
        from ...core.update_checker import check_for_update

        self._update_btn.configure(state="disabled", text="Checking...")
        self._update_status.configure(text="Checking GitHub releases...", text_color="#95a5a6")

        def _callback(release) -> None:
            def _show() -> None:
                self._update_btn.configure(state="normal", text="Check for Updates")
                self._update_status.configure(
                    text=f"v{release.version} is available.",
                    text_color="#2d8a4e",
                )
                self.app._show_update_banner(release)

            self.after(0, _show)

        def _on_no_update() -> None:
            def _show() -> None:
                self._update_btn.configure(state="normal", text="Check for Updates")
                self._update_status.configure(
                    text=f"You're up to date on v{__version__}.",
                    text_color="#95a5a6",
                )

            self.after(0, _show)

        def _on_error(message: str) -> None:
            def _show() -> None:
                self._update_btn.configure(state="normal", text="Check for Updates")
                self._update_status.configure(
                    text=f"Could not check for updates: {message}",
                    text_color="#c0392b",
                )

            self.after(0, _show)

        check_for_update(__version__, _callback, _on_no_update, _on_error)

    def _open_backup_storage(self) -> None:
        folder = self.app.backup.backup_root
        if folder.is_dir():
            os.startfile(str(folder))

    def _open_data_folder(self) -> None:
        from ..app_window import DEFAULT_DATA_DIR

        if Path(DEFAULT_DATA_DIR).is_dir():
            os.startfile(str(DEFAULT_DATA_DIR))
