Windrose Mod Manager v0.8.1

Short Nexus file changelog

- Renamed the import button to `Add Mod Files...` so first-time users can find it faster.
- Added `Add Folder...` and shallow folder scanning for supported mod files.
- Updated the Mods empty state to explain that downloads can be on any drive.
- Folder import/drop now finds `.zip`, `.7z`, `.rar`, `.pak`, `.utoc`, and `.ucas` files directly inside the selected folder and one level below.
- Loose pak companions still bundle together through the existing safe import flow.
- Hosted setup now uses clearer `Server Folder` wording and shows concrete path examples.
- Added a conservative `Nitrado FTP` preset: FTP, port 21, Server Folder `windrose`, Mods Folder Override `windrose/Mods`.
- Hosted setup now previews resolved mods, settings, and save paths before saving.

Sticky update

v0.8.1 is live.

This is a focused usability patch for adding mods and setting up hosted FTP paths.

What changed in v0.8.1

- Use `Add Mod Files...` in the Mods tab to import downloaded mod archives.
- You can import mods from any drive or folder. Your game can be on one drive and your downloads on another.
- Use `Add Folder...` or drag/drop a folder to scan for supported mod files.
- Folder scans look directly inside the selected folder and one level below it, so common extracted mod folders work without scanning a whole drive.
- Extracted `.pak`, `.utoc`, and `.ucas` files should still be selected/dropped together so the manager can bundle companions correctly.

Hosted / Nitrado note

- Hosted setup now shows clearer `Server Folder` examples.
- If FTP shows `windrose/R5`, use Server Folder `windrose`.
- If FTP opens directly inside the Windrose server folder and you see `R5` immediately, use Server Folder `.`.
- For Nitrado FTP, try the new `Nitrado FTP` preset. It uses FTP port 21, Server Folder `windrose`, and uploads pak mods to `windrose/Mods`.
- If your Nitrado FTP browser does not show `windrose/Mods`, clear `Mods Folder Override` and use the normal derived `R5/Content/Paks/~mods` path instead.
- Use the FTP credentials from your provider panel. Query, Game, and RCON ports are not FTP ports.

Not changed in this release

- Generic hosted defaults are unchanged.
- This does not add Thunderstore/Gale integration.
- This does not add remote path auto-detection or the broader config center.

Release zip SHA256

`E8BBCEA1A2880B1C59A48F2F7AC54A1AC9990B0AB7EC574DCC1DA23F56939311`
