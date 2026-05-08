## Windrose Mod Manager v0.7.1

Windrose Mod Manager v0.7.1 is a focused trust and sync patch on top of v0.7.0. It adds clearer archive/install review text, improves diagnostics, fixes variant/component sync behavior, and cleans duplicate active manifest rows from repeated same-target installs.

### Highlights

- Added archive summaries in Mods.
- Added pre-install and hosted upload review text before writes.
- Added Copy Diagnostics wording and included the latest install/upload review in diagnostics.
- Added an `All variants` option for detected multi-pak variant archives.
- Fixed variant companion planning so selected `.pak`, `.utoc`, and `.ucas` files stay together.
- Fixed selected bundle/component installs so sync preserves the exact client setup.
- Fixed Review Sync Actions so selected client mods can sync directly to Local Server or Dedicated Server.
- Cleaned duplicate active manifest rows caused by repeated installs of the same target/source/variant/files.
- Kept external/host-managed UE4SS behavior from v0.7.0.

### Notes

- The recommended local/dedicated sync flow is Dashboard -> Run Compare -> Review Sync Actions -> Apply Selected.
- Hosted sync with selected bundle components is still conservative; use hosted upload review for those cases.
- The host-managed UE4SS path from v0.7.0 is unchanged.

### Validation

- `python -m compileall windrose_deployer -q`
- `python -m pytest -q` -> `262 passed`
- Source GUI smoke across Dashboard, Mods, Server, Activity, Settings, and Help
- Packaged exe smoke launch confirmed v0.7.1 identity and startup

### SHA256

Release zip: `A62F3C6A167368C3065A856FA1F887F6B935A405588E08910AD4ECCEF23A947D`

### Full Changelog

https://github.com/Vercadi/windrose-mod-manager/compare/v0.7.0...v0.7.1
