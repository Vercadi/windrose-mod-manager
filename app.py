"""Windrose Mod Deployer — entry point."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from windrose_deployer.ui.app_window import AppWindow


def main() -> None:
    app = AppWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
