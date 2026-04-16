# Nexus Release Copy - v0.3.0

## File Page Changelog

Windrose Mod Manager v0.3.0

This update focuses on the app's biggest differentiator: safe Windrose client + server management, including hosted server support.

Main additions

- Hosted server support over SFTP / SSH with saved profiles
- Install mods to hosted servers directly from the Mods workspace
- Hosted server settings editing for `ServerDescription.json` and `WorldDescription.json`
- New Recovery Center with restore, undo-friendly history, raw backup access, and cleanup tools
- Better client / server sync review for both local and hosted setups
- Cleaner Mods workspace with archive and applied-mod visibility in one place
- Launch Windrose and Launch Local Server shortcuts
- GitHub update notifications with direct download link

Important fixes

- Apply and Restart no longer continues after a failed save
- Sync compare no longer drops installs that share the same display name
- Recovery timeline no longer double-lists config saves
- Variant chooser now scrolls properly for large multi-option archives
- Uninstall still restores overwritten originals safely

Hosted server note

Hosted support requires a provider that gives you SFTP / SSH access to the server files. If your host does not expose that, the hosted workflow in the app will not work.

---

## Sticky Comment

v0.3.0 is live.

This is the update for everyone who asked about rented / third-party server support.

What is new in v0.3.0

- Hosted server support over SFTP / SSH with saved profiles
- Install mods to hosted servers directly from the Mods workspace
- Hosted `ServerDescription.json` and `WorldDescription.json` editing from inside the app
- Recovery Center with restore, undo-friendly history, raw backup access, and cleanup tools
- Better client / server sync review for local and hosted setups
- Cleaner Mods workspace with applied-mod visibility and hosted live inventory
- Scrollable variant chooser for long multi-option mod archives
- GitHub update notifications with direct download link

Important fixes in this release

- Apply and Restart no longer continues after a failed save
- Sync compare no longer drops same-name installs
- Recovery timeline no longer double-lists config saves

Hosted server requirements

- Your provider must give you SFTP / SSH file access
- You will usually need host, port, username, password or private key, and the server folder path
- If your host only gives a web panel and no file access, this part will not work

If you already have the app, the new version should appear through the in-app GitHub update check once the GitHub release is live.

If you hit issues, post in the comments or open an issue on GitHub with as much detail as you can.
