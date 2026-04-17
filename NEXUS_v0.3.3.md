# Nexus Release Copy - v0.3.3

Use this for the Nexus file changelog / update post.

---

Windrose Mod Manager v0.3.3

This is a UX and readability hotfix focused on making the manager easier to scan, less popup-heavy, and more comfortable across different screen densities.

What is fixed in v0.3.3

- Restored bundled/local server support and correctly split bundled server, dedicated server, and hosted server workflows
- The app now treats the main game's `R5\Builds\WindowsServer` files separately from the standalone **Windrose Dedicated Server** install
- Added a new **UI Size** setting with Compact, Default, and Large
- Added a new **Confirmation Behavior** setting with Always Confirm, Destructive Actions Only, and Reduced Confirmations
- Replaced a number of routine success popups with inline result messages
- Tightened button sizing and row density across the main workspace
- Improved readability in Library, Server, Recovery, Settings, Help, and the Technical Log
- UI Size now changes readability and density without resizing the outer app window
- Behavior settings now use proper user-facing labels and preview immediately
- The Behavior tab now scrolls properly instead of clipping helper text
- Settings helper text wraps more cleanly in the updated layout

Why this matters

This hotfix restores the intended bundled/local server workflow while also making the app feel calmer and easier to read. It improves day-to-day usability without changing the core managed install, recovery, or hosted-server model.

Validation

- `python -m py_compile windrose_deployer\ui\app_window.py windrose_deployer\ui\tabs\settings_tab.py`
- `python -m pytest tests/test_ui_preferences.py --basetemp ... -o cache_dir=...` -> 8 passed

Download

Grab v0.3.3 from the main files section or from GitHub Releases.
