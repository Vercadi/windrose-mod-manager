Windrose Mod Manager v0.6.4

Short Nexus file changelog

- Added redacted Support Info export from the Help tab.
- Hosted setup now trims hidden spaces from host, username, and path fields before testing/saving.
- Hosted tests now show the normalized protocol, host, port, and username before connecting.
- Support info includes app version, target paths, hosted profile context, recent activity/log tail, manifest counts, framework state, and last hosted diagnostics without passwords/private keys.
- Improved framework status wording, especially RCON installed as version.dll before windrosercon/settings.ini is generated.
- Compare/sync now treats server-only framework tooling more clearly and does not offer client sync for intentional server-only packages.
- Activity tab avoids raw backup scans unless the raw backup browser is opened.

Sticky update

May 2:
v0.6.4 is live.

This is a small stabilization and support-quality update after the recent hosted/framework releases. It does not add major new features; it mainly makes troubleshooting easier and reduces confusing status messages.

What changed in v0.6.4
- Added redacted Support Info export in Help.
- Support Info can be copied or saved and includes useful troubleshooting details without passwords/private keys.
- Hosted setup now trims hidden spaces from Host, Username, Server Folder, and override fields before testing/saving.
- Hosted connection tests now show the normalized FTP/SFTP target before connecting.
- Last hosted connection diagnostics are included in Support Info.
- RCON framework status is clearer when only version.dll is installed and windrosercon/settings.ini has not been generated yet.
- Compare/sync wording is clearer for server-only framework tooling such as RCON and WindrosePlus.
- The app no longer offers client sync actions for packages that are intentionally server-only.
- Activity stays lighter for large histories and avoids raw backup scans until the raw backup browser is opened.

Nitrado / hosted reminder
For Nitrado, use the FTP Credentials section from the provider panel:
- Protocol: FTP
- Host / IP: the FTP hostname, for example ms2084.gamedata.io
- Port: 21
- Username: the FTP username
- Password: the FTP password

Do not use Query Port, RCON Port, or the game/server port as the FTP port.

If something fails, open Help -> Copy Support Info and paste that with your issue. It should not include passwords or private key contents, but please still review it before posting publicly.

This update does not add FTPS, Nexus downloading, load order, retoc, or new RCON admin controls.
