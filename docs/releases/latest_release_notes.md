## Windrose Mod Manager v0.8.1

Windrose Mod Manager v0.8.1 is a focused usability patch for two common setup pain points: adding mods from anywhere on the PC, and configuring hosted FTP paths for providers such as Nitrado.

### Highlights

- Renamed the inactive mod import action to `Add Mod Files...`.
- Added `Add Folder...` and shallow folder scanning for supported mod files.
- Made the Mods empty state explain that downloads can be on any drive.
- Folder import/drop now finds `.zip`, `.7z`, `.rar`, `.pak`, `.utoc`, and `.ucas` files directly inside the selected folder and one level below it.
- Loose pak companion imports still use the existing manager-owned bundle flow.
- Hosted setup now uses clearer `Server Folder` wording with concrete examples for `windrose/R5` and direct `R5` logins.
- Added a conservative `Nitrado FTP` preset: FTP, port `21`, `Server Folder = windrose`, and `Mods Folder Override = windrose/Mods`.
- Hosted setup now shows resolved path previews for mods upload, server settings, and world saves.
- Help and first-run copy now point users toward `Add Mod Files...`, folder import, and hosted path examples.

### Notes

- Generic hosted defaults are unchanged. Without a provider override, `Server Folder = windrose` still derives mods to `windrose/R5/Content/Paks/~mods`.
- The Nitrado preset is editable. If a user's FTP browser does not show `windrose/Mods`, they can clear `Mods Folder Override` and use the normal derived path.
- This release does not add remote path auto-detection, Thunderstore/Gale integration, or the broader config center.

### Validation

- `python -m compileall windrose_deployer -q`
- `python -m pytest -q` -> `295 passed`
- Source GUI smoke across Dashboard, Mods, Server, Activity, Settings, and Help
- Source import smoke for archive import and folder import with loose pak companions
- Source hosted setup smoke for the `Nitrado FTP` preset and resolved path guidance
- Remote deployment planner smoke confirmed Nitrado uploads target `windrose/Mods`
- Packaged exe smoke launch confirmed v0.8.1 identity and startup

### SHA256

Release zip: `E8BBCEA1A2880B1C59A48F2F7AC54A1AC9990B0AB7EC574DCC1DA23F56939311`

### Full Changelog

https://github.com/Vercadi/windrose-mod-manager/compare/v0.8.0...v0.8.1
