Windrose Mod Manager v0.5.2

Short Nexus file changelog

- Dashboard compare now lets you choose Local Server, Dedicated Server, or Hosted Server directly.
- Added preview-first Review Sync Actions for safe client-to-server fixes after compare.
- Missing client mods can be installed to Local/Dedicated Server or uploaded to Hosted from the Dashboard review flow.
- Server-only / hosted-only files are listed for review but are not auto-deleted.
- Manifest drift now appears on the Dashboard instead of only in the technical log.
- Activity / Backups wording is cleaner and no longer refers to the old Recovery tab name.
- Activity refresh is lighter for larger histories.
- Startup/discovery is safer when old saved Steam paths point to missing or inaccessible drives.
- FTP hosted path checks are more compatible with servers that do not support all FTP commands.
- Hosted path errors now explain FTP-root-relative paths, including Nitrado-style setups.
- Fixed a Dashboard status color issue where Not running could look healthy.
- Fixed failed hosted Dashboard sync recording a successful upload in Activity.

Sticky update

April 22:
v0.5.2 is live.

This is a polish and trust update for v0.5.1. It keeps the new Dashboard and FTP hosted support, and focuses on making compare/sync review clearer, hosted path errors easier to understand, and startup/discovery safer.

What's new in v0.5.2
- Dashboard compare now has its own target selector:
  - Local Server
  - Dedicated Server
  - Hosted Server
- Run Compare updates the Dashboard parity card for the selected target.
- Open Full Compare still opens the detailed Server compare view.
- New Review Sync Actions flow after compare:
  - installs missing client mods to Local Server where safe
  - installs missing client mods to Dedicated Server where safe
  - uploads missing client mods to Hosted Server where safe
  - lists server-only / hosted-only files for review instead of auto-deleting them
- Manifest drift now appears on the Dashboard instead of only in the technical log.
- Activity / Backups wording is cleaner across the app.
- Activity refresh should feel lighter on larger histories.
- Startup/discovery is safer if an old saved Steam path points to a missing or inaccessible drive.
- FTP hosted path checks are more compatible with servers that do not support every FTP command.
- Hosted path errors now explain FTP-root-relative paths, including Nitrado-style setups.

Safety fixes
- Failed hosted Dashboard sync no longer records a successful hosted upload in Activity.
- Dashboard status coloring no longer treats Not running as a healthy/running state.

Hosted notes
- Hosted support still works over SFTP.
- Hosted support also works over FTP for file actions.
- FTP is file-transfer only:
  - inventory
  - upload
  - delete
  - file-based config access where supported
- FTP does not support restart-command automation. Restart from your host panel unless you use SFTP/SSH with a restart command.

Quick FAQ

What is Local Server?
Local Server means the bundled server files inside the main Windrose install:
R5\Builds\WindowsServer

What is Dedicated Server?
Dedicated Server means the separate Steam Windrose Dedicated Server app install.

What is Hosted Server?
Hosted Server means a remote/rented server you connect to from your own PC.

Do gameplay mods usually need to be on both client and server?
Usually yes. Gameplay/content mods generally belong on the server and on every player's client. UI/visual/client-only mods usually only belong on the client.

Does Review Sync Actions automatically delete anything?
No. It is preview-first. Safe missing client-to-server installs/uploads can be selected, but server-only or hosted-only removals are only listed for review.

Antivirus / VirusTotal note
A few users have reported antivirus/ML detections on the packaged exe. At the moment this still appears to be a false-positive pattern related to the unsigned packaged Python build, not known malicious behavior. The source code is public on GitHub, and release hashes are available if you want to verify the download yourself.

If you run into issues, post in the comments or open an issue on GitHub. For hosted issues, include your provider name, whether you used FTP or SFTP, and the exact step that failed.

Hosted quick setup sticky

Hosted / rented server quick setup

Use Hosted Server only for remote/rented servers you connect to from your own PC.

1. Open Server and switch to Hosted Server.
2. Open Hosted Setup.
3. Choose the correct protocol:
- SFTP if your provider gives you SFTP / SSH details.
- FTP if your provider gives you FTP details.

4. Enter the Host / IP, port, username, and password exactly as shown by your provider panel.
5. Set Server Folder to the Windrose server folder as seen through your file login.

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

Provider notes
- Host Havoc may expose either FTP Info or SFTP Info depending on your panel/service.
- Indifferent Broccoli uses FTP on port 21.
- Nitrado uses FTP file access; use the FTP credentials and paths from the FTP view.

Restart note
- FTP support is file-transfer only.
- If your host does not support restart commands through SFTP/SSH, restart from the host panel instead.

If a hosted setup fails, include:
- provider name
- FTP or SFTP
- port used
- Server Folder value
- Mods Folder Override value, if any
- the exact error text
