Windrose Mod Manager v0.6.1

Short Nexus file changelog

- Fixed UE4SS / framework uninstall lifecycle so source archives return to Inactive Mods correctly.
- Dashboard framework state now refreshes after framework install/uninstall actions.
- Added manager-owned archive library copies for imported `.zip`, `.7z`, and `.rar` files, so installs still work if the original download is deleted.
- Duplicate imported archives now reuse an existing manager-owned copy when the file hash matches.
- Added proper WindroseRCON `version.dll` archive handling and routing to `R5\Binaries\Win64`.
- RCON and WindrosePlus are blocked from Client install targets, and invalid client presets are hidden/disabled.
- Added Frameworks management actions for UE4SS, RCON, and WindrosePlus.
- Added known config editing for UE4SS settings, RCON settings, and WindrosePlus config files with backup-before-save.
- Added WindrosePlus install, rebuild, dashboard, launch, stop, and restart actions.
- WindrosePlus JSON editing now formats JSON clearly and validates before save.
- Dashboard Frameworks layout is more compact and easier to scan.

Sticky update

April 25:
v0.6.1 is live.

This is a framework support hotfix / polish update for v0.6.0. It mainly improves UE4SS, RCON, and WindrosePlus workflows and fixes a few rough edges from the first framework-support release.

What's new / fixed in v0.6.1
- UE4SS runtime and UE4SS mod uninstall now return the source archive to Inactive Mods correctly.
- Dashboard framework status refreshes after install/uninstall actions.
- Imported `.zip`, `.7z`, and `.rar` files are now copied into the manager's own archive library by default.
- If you delete the original file from Downloads later, the manager can still reinstall from its own copy.
- Duplicate archive imports reuse the existing manager copy when the hash matches.
- WindroseRCON archives that contain only `version.dll` are now handled correctly.
- RCON installs to `R5\Binaries\Win64`, matching the mod author's setup instructions.
- RCON and WindrosePlus are blocked from Client installs.
- Invalid Client / Client + Server presets are hidden or blocked for server-only framework packages.
- Frameworks management now includes known actions for:
  - UE4SS Runtime
  - RCON
  - WindrosePlus
- Known config editing was added for:
  - UE4SS-settings.ini
  - WindroseRCON settings.ini
  - windrose_plus.json
  - WindrosePlus override ini files
- Config saves create backups first.
- WindrosePlus support now includes:
  - Run WindrosePlus Install
  - Open WindrosePlus Folder
  - Open WindrosePlus Dashboard
  - Rebuild WindrosePlus Overrides
  - Launch WindrosePlus Server
  - Stop WindrosePlus Server
  - Restart WindrosePlus Server
  - Stop WindrosePlus Dashboard
- WindrosePlus JSON editing now formats the file clearly instead of showing one long line.
- Dashboard Frameworks layout is more compact.

Important framework notes
- UE4SS, WindrosePlus, and RCON are not bundled with the manager.
- You still import the user-supplied archives yourself.
- WindrosePlus and RCON are treated as server-side tools.
- Do not install WindrosePlus or RCON to Client.
- UE4SS can be client or server depending on what the UE4SS mod author requires.
- For WindrosePlus, use the WindrosePlus launch wrapper if you want its rebuild/start workflow.

Hosted notes
- Hosted FTP/SFTP support can upload framework files, but running scripts or launch wrappers depends on what your host allows.
- FTP is file-transfer only.
- Hosted restart automation still requires SFTP/SSH command support or your host panel.

Quick FAQ

Do gameplay mods still need to be on both client and server?
Usually yes. Gameplay/content pak mods generally belong on the server and on every player's client. UI/visual/client-only mods usually only belong on the client.

Do UE4SS / RCON / WindrosePlus need to be on the client?
Not usually. WindrosePlus and RCON are server-side. UE4SS depends on the specific UE4SS mod.

What should I upload for this version?
Upload the release zip from the manager release folder, not the whole build folder.

Antivirus / VirusTotal note
A few users have reported antivirus/ML detections on the packaged exe. At the moment this still appears to be a false-positive pattern related to the unsigned packaged Python build, not known malicious behavior. The source code is public on GitHub, and release hashes are available if you want to verify the download yourself.

If you run into issues, post in the comments or open an issue on GitHub. For hosted issues, include your provider name, FTP or SFTP, Server Folder value, Mods Folder Override value if used, and the exact error text.

Hosted quick setup sticky

Hosted / rented server quick setup

Use Hosted Server only for remote/rented servers you connect to from your own PC.

1. Open Server and switch to Hosted Server.
2. Open Hosted Setup.
3. Choose the correct protocol:
- SFTP if your provider gives you SFTP / SSH details.
- FTP if your provider gives you FTP details.

4. Enter the Host / IP, port, username, and password exactly as shown by your provider panel.
5. Set Server Folder to the Windrose server folder as seen through your FTP/SFTP login.

Common examples:
- /home/container
- /games/windrose
- C:/server/Windrose
- . if the FTP/SFTP login already opens inside the Windrose server folder

Important for FTP hosts such as Nitrado:
- Paths are usually relative to the FTP login root.
- Do not use a path copied from the web panel if it does not match what you see in an FTP client.
- If your FTP login opens directly inside the Windrose server folder, try Server Folder = "." and leave Mods Folder Override blank.
- If you use Mods Folder Override, try:
  R5/Content/Paks/~mods

6. Click Test Connection.
7. Click Load Current Settings to verify the app can read hosted config files.
8. Install/upload mods to Hosted Server from the manager.
9. Use Dashboard or Server compare to check client/server parity.

Mod placement rule of thumb
- Hosted/rented server: install gameplay mods to Hosted Server and to every player's Client.
- Local Server: install gameplay mods to Client + Local Server.
- Dedicated Server app: install gameplay mods to Client + Dedicated Server.
- Friends usually need the same gameplay/content mods on their own client unless the mod author says it is server-only.

Framework note
- UE4SS / RCON / WindrosePlus hosted support can upload files, but activation may require server-side script/start support from your host.
- WindrosePlus and RCON are server-side tools, not client mods.

If a hosted setup fails, include:
- provider name
- FTP or SFTP
- port used
- Server Folder value
- Mods Folder Override value, if any
- the exact error text
