Windrose Mod Manager v0.5.1 focuses on faster startup, a more useful operations-first Dashboard, and broader hosted-server support for the providers people are actually asking about.

What's new in v0.5.1

- Faster startup:
  - the app now opens first and finishes secondary refresh work after the main window is already usable
  - non-visible tabs now lazy-load instead of doing a full eager refresh on boot
  - path reconciliation is lighter when your saved paths are already valid
- Dashboard is now a real operations home instead of a loose summary:
  - clear status for Windrose, Local Server, Dedicated Server, and Hosted
  - current source, world, hosted profile, and recent backup/apply state
  - mod counts by target
  - quick actions for launch, folder access, backup, and compare
- Hosted server support now covers both:
  - SFTP
  - FTP
- Better provider support for real user setups:
  - Host Havoc users can use the FTP Info or SFTP Info from the panel exactly as shown
  - Indifferent Broccoli users can now use FTP on port 21
- Hosted setup is clearer:
  - protocol selector (`SFTP` or `FTP`)
  - `Host / IP` wording instead of implying a panel URL
  - explicit provider ports are preserved
  - clearer protocol mismatch messages
- FTP hosted support is honest about capability:
  - file access works
  - restart commands are not claimed for FTP
- Activity / Backups improvements:
  - raw backup browser now lazy-loads
  - `Delete Selected` and `Delete All` were added for raw backup cleanup
- Dashboard compare flow is cleaner:
  - `Run Compare` updates parity on the Dashboard
  - `Open Full Compare` takes you to the detailed Server compare view
- Dashboard `Last Apply` now reflects actual apply/save actions instead of launches/backups

Safety / compatibility notes

- Existing hosted profiles without a protocol field continue to load as `SFTP`
- Existing hosted backup/recovery records using older `sftp://...` identity remain compatible
- Existing SFTP hosted workflows are preserved
- FTP is intentionally file-transfer only in v0.5.1:
  - hosted inventory
  - upload
  - delete
  - file-based config access where supported
- FTP does not provide restart-command support in this release

Suggested sticky update

April 19:
v0.5.1 is live.

This update is focused on three things:
- faster startup / less heavy-feeling app launch
- a more useful Dashboard as an operations home
- broader hosted-server support, especially for Host Havoc and Indifferent Broccoli style setups

What v0.5.1 adds
- Faster startup with lighter boot refresh behavior
- New Dashboard with status, current setup, parity summary, and quick actions
- Hosted setup now supports both SFTP and FTP
- Better support for real provider setups:
  - Host Havoc: use the FTP Info or SFTP Info from your panel
  - Indifferent Broccoli: use FTP on port 21
- Clearer hosted setup wording and protocol mismatch feedback
- Better Activity / Backups cleanup actions
- Dashboard compare summary now updates in place

Quick FAQ

What is the difference between Local Server, Dedicated Server, and Hosted Server?
- Local Server = the bundled WindowsServer files inside the main Windrose install
- Dedicated Server = the separate Steam `Windrose Dedicated Server` app
- Hosted Server = a remote/rented server you connect to from your own PC

Does hosted support still work with SFTP/SSH?
- Yes. Existing SFTP support is still there and remains fully supported.

What does FTP support add?
- FTP support is for hosted file access on providers that do not expose SFTP for your plan/setup.
- In v0.5.1, FTP supports hosted file actions like listing, upload, delete, and file-based config access where available.
- FTP does not support restart-command automation in this release.

Does `Run Compare` sync mods automatically?
- No. Compare is a review tool. It checks client vs. the currently active server target and shows whether things look clean or need review.

If you run into hosted issues, please include:
- host/provider name
- whether you used FTP or SFTP
- the exact host/IP and port style from your panel
- the step that failed

Suggested second sticky / quick guide

Hosted quick setup guide

Use `Hosted Server` only for remote/rented servers you connect to from your own PC.

1. Open `Server > Hosted Server > Hosted Setup`
2. Pick the correct protocol:
- `SFTP` if your host gives you SFTP / SSH details
- `FTP` if your host gives you FTP details
3. Enter the `Host / IP` exactly as shown by the provider
4. Keep the provider port exactly as shown:
- SFTP usually uses 22 unless your panel says otherwise
- Indifferent Broccoli uses FTP on port 21
5. Set the correct remote server folder
6. Test connection
7. Use `Run Compare`, install/upload mods, and refresh hosted inventory from inside the app

Important:
- FTP support is file-transfer only in v0.5.1
- restart-command support still requires SFTP/SSH-style command access

Suggested modpage short description

A standalone Windrose mod manager for client play, local hosting, dedicated servers, and hosted/rented servers. Supports archive import, tracked installs/uninstalls, backups/recovery, server/world settings editing, and hosted deployment over SFTP or FTP.

Suggested modpage feature list refresh

- Managed installs for:
  - Client
  - Local Server
  - Dedicated Server
  - Hosted Server
- Archive library with tracked install state
- Variant-aware install for multi-option pak archives
- Expandable bundle-aware mod cards for larger modular archives
- Automatic backups and in-app recovery tools
- Activity / history view for installs, restores, applies, and hosted actions
- Dashboard with server/client status, parity summary, and quick actions
- Hosted deployment over:
  - SFTP
  - FTP
- Built-in editing for:
  - `ServerDescription.json`
  - `WorldDescription.json`
- Client/server/hosted parity review tools
- Local, dedicated, and hosted mod folder visibility from inside the app

Suggested image/banner notes

Best screenshots to update for v0.5.1:
- Dashboard showing the new 4-card layout
- Hosted Setup showing the `Protocol` selector and `Host / IP` wording
- Activity / Backups showing cleanup controls
- Mods screen with current target filters and cleaner applied/archive split

Good banner angle:
- "Client + Server + Hosted in one Windrose cockpit"
or
- "Manage Windrose mods across client, dedicated, and hosted servers"
