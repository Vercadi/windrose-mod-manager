Windrose Mod Manager v0.4.0 focuses on clearer install targets, cleaner applied/archive visibility, better local/dedicated/hosted separation, and safer multi-target mod management.

What's new in v0.4.0

- Replaced vague install target wording with clearer names:
  - Client
  - Local Server
  - Dedicated Server
  - Hosted Server
- Replaced `Both` with explicit install presets:
  - Client only
  - Client + Local Server
  - Client + Dedicated Server
  - Local Server only
  - Dedicated Server only
  - Hosted Server only
- Reworked the Mods screen around clearer `Applied Mods` and `Archives` sections
- Added target scope filters directly in Mods:
  - All
  - Client
  - Local Server
  - Dedicated Server
  - Hosted Server
- Archives now default to `Available Archives`, so already-applied source archives are hidden from the main archive list until uninstalled
- Added inline archive install menus and reduced extra install popups
- Added multi-select install and uninstall actions in the Mods workspace
- Added real live `~mods` folder scanning for client, local server, dedicated server, and hosted server targets
- Hosted server mods can now be selected and uninstalled from the Mods screen
- Added `Install To...` on applied rows so existing installs can be extended to additional targets later
- Added direct folder-opening actions from archive, applied, and live-item menus
- Increased the default app window size for a better fit
- The large Mods details tray is now hidden by default and can be opened only when needed
- Welcome dialog now only auto-shows on first run and has a `Don't show this again` option
- Remaining dialogs now open centered over the app window

Safety / under-the-hood improvements

- Combined multi-target install presets are now transactional and roll back completed targets if a later target fails
- `Client + Local Server` and `Client + Dedicated Server` installs now create separate target records instead of one ambiguous combined record
- Older combined client/local installs are normalized into separate records automatically when possible
- Live unmanaged UE5 bundles now group `.pak`, `.utoc`, and `.ucas` companion files together as one item
- Unmanaged live content now uses the normal applied-mod uninstall workflow instead of a separate removal UI
- Recovery, sync, and target summaries now use the updated target terminology throughout the app
- Added regression coverage for target labels, combined install rollback, live mod inventory, hosted live uninstall, and welcome/settings preference persistence

Known note

- UPX remains disabled in the PyInstaller build to reduce heuristic antivirus false positives on unsigned Windows builds
- Some antivirus engines may still produce low-confidence static-ML false positives on bundled Python runtime modules; the source code and release hashes are public for verification
