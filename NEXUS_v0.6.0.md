Windrose Mod Manager v0.6.0

Short Nexus file changelog

- Added first-pass UE4SS runtime support.
- Added UE4SS mod detection and install routing.
- Added WindroseRCON / RCON mod detection and install routing.
- Added WindrosePlus package detection and server-only install support.
- Framework installs now use the correct `R5\Binaries\Win64` / `ue4ss\Mods` paths instead of being treated like pak mods.
- Dashboard now has a separate Frameworks card for UE4SS, RCON, and WindrosePlus status.
- Client/server compare no longer warns that server-only framework packages such as WindrosePlus must be installed on the client.
- Hosted uploads can now route UE4SS/framework files to their proper remote paths over FTP/SFTP.
- Imported loose `.pak`, `.utoc`, and `.ucas` files are grouped as one inactive mod when they belong together.
- Active / Inactive wording replaces the older Applied / Archive wording in the Mods screen.
- Activity/history now records framework install kinds more clearly.

Sticky update

April 24:
v0.6.0 is live.

This update adds first-pass UE4SS and server-framework support while keeping the manager focused on normal Windrose mod management.

What's new in v0.6.0
- UE4SS runtime archives can now be detected and installed to the correct `R5\Binaries\Win64` location.
- UE4SS mods can now be detected and installed to `R5\Binaries\Win64\ue4ss\Mods`.
- WindroseRCON-style mods are detected as RCON mods instead of normal pak mods.
- WindrosePlus packages are detected as server-only framework packages.
- Dashboard now shows framework status separately:
  - UE4SS Runtime
  - RCON
  - WindrosePlus
- WindrosePlus and RCON are treated as server-side framework items, so compare/sync no longer tells you to install them on the client.
- Hosted uploads can route UE4SS/framework files to the proper remote server folders over FTP/SFTP.
- The Mods screen now uses clearer Active Mods / Inactive Mods wording.
- Loose `.pak`, `.utoc`, and `.ucas` files can be imported directly and grouped as one mod when they belong together.
- Activity/history now labels framework installs more clearly.

Important UE4SS notes
- UE4SS itself is not bundled with the manager.
- You still need to provide/download the UE4SS archive yourself.
- UE4SS support is path/install support, not a guarantee that every UE4SS mod works with every Windrose setup.
- If a UE4SS mod requires the runtime, install UE4SS Runtime first.

WindrosePlus notes
- WindrosePlus is server-side only in this manager.
- It should be installed to Local Server or Dedicated Server, not Client.
- The manager can place/detect the package files, but WindrosePlus activation still depends on its own install/start workflow.
- Hosted/rented WindrosePlus support may depend on whether your host allows the required scripts/start workflow.

Hosted notes
- Hosted support works over SFTP and FTP for file actions.
- FTP is file-transfer only; restart commands still require SFTP/SSH support or your host panel.
- For hosted UE4SS/WindrosePlus setups, file upload may not be enough if the host does not allow the needed runtime/start behavior.

Quick FAQ

Do gameplay mods still need to be on both client and server?
Usually yes. Gameplay/content pak mods generally belong on the server and on every player's client. UI/visual/client-only mods usually only belong on the client.

Do UE4SS / RCON / WindrosePlus need to be on the client?
Not usually. WindrosePlus and RCON are treated as server-side framework items. UE4SS runtime/mods depend on what the mod author says.

Can WindrosePlus be installed on hosted servers?
The manager can upload the files to hosted servers, but hosted activation depends on the provider. Some hosts may not allow the scripts/start workflow WindrosePlus needs.

Antivirus / VirusTotal note
A few users have reported antivirus/ML detections on the packaged exe. At the moment this still appears to be a false-positive pattern related to the unsigned packaged Python build, not known malicious behavior. The source code is public on GitHub, and release hashes are available if you want to verify the download yourself.

If you run into issues, post in the comments or open an issue on GitHub. For hosted issues, include your provider name, FTP or SFTP, Server Folder value, Mods Folder Override value if used, and the exact error text.
