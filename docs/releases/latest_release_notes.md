## Windrose Mod Manager v0.6.6

Windrose Mod Manager v0.6.6 is a local cleanup and QoL release. It includes the unreleased v0.6.5 selection/profile improvements plus a new local-only Restore Vanilla workflow.

### Highlights

- Added `Restore Vanilla` for Client, Local Server, and Dedicated Server.
- Restore Vanilla previews managed mods, unmanaged `~mods` bundles, and known UE4SS/RCON/WindrosePlus framework files before removal.
- Restore Vanilla backs up unmanaged and framework files first, and does not touch saves, server settings, hosted files, inactive archives, or backup history.
- Added `Select All` for Active Mods and Inactive Mods, scoped to the current target/filter/search instead of blindly selecting everything.
- Improved Profiles workflow with clearer `New`, `Save as New`, and `Update Selected` actions.
- Profile apply no longer removes extra active mods unless the new removal checkbox is explicitly enabled.
- Hosted profile entries remain review-only in mod Profiles.
- Restore Vanilla backups now use a separate `backups/restore_vanilla` area.

### Notes

- Hosted/remote Restore Vanilla is intentionally deferred.
- This does not add load order, Nexus downloads, retoc/configurable overhaul, FTPS, or RCON admin commands.
- Framework cleanup is unchecked by default because it can remove UE4SS, RCON, and WindrosePlus files.

### Validation

- `python -m compileall windrose_deployer -q`
- `python -m pytest -q` -> `240 passed`
- `git diff --check`

### SHA256

`F132F96F344FDA1CDE4E0FC1929884C0DD423269EEC6CE89C8590D8C2E661052`

### Full Changelog

https://github.com/Vercadi/windrose-mod-manager/compare/v0.6.4...v0.6.6
