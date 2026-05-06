## Windrose Mod Manager v0.7.0

Windrose Mod Manager v0.7.0 is a stability, hosted-server, and usability release. It focuses on making UE4SS-dependent hosted mod workflows usable when UE4SS is already managed by the host/provider, while also improving startup performance and fixing the v0.7 preview lazy-tab issues.

### Highlights

- Added external/host-managed UE4SS support for local, dedicated, and hosted targets.
- Hosted profiles can now mark UE4SS as managed by the host/provider, including manually installed or experimental GitHub UE4SS builds.
- UE4SS-dependent mods can be installed/uploaded without the manager replacing a working external UE4SS runtime.
- Dashboard now starts much faster by building only the Dashboard at startup.
- Mods, Server, Activity, Settings, and Help load lazily on first use.
- Added visible loading placeholders for lazy-loaded tabs.
- Fixed blank tab and fatal lazy-load crashes from early v0.7 testing.
- Fixed text clipping and wrapping issues in Mods and Server panes.
- Fixed a Mods tab layout feedback loop that could cause repeated redraws and crashes.
- Reduced visible hitches by avoiding Server auto-prewarm, avoiding duplicate Mods library loads, using cached Server process checks, and delaying heavy manifest drift scans.

### Notes

- This release does not make the broken Nexus UE4SS runtime work by itself.
- If a host/provider already has a working UE4SS runtime installed, mark UE4SS as external/host-managed and use the manager to install UE4SS mods without replacing that runtime.
- Server first open can still take a moment because the full Server UI is built on first selection. It no longer blocks initial startup or runs as an automatic post-start prewarm.
- Hosted/remote Restore Vanilla is still deferred.

### Validation

- `python -m compileall windrose_deployer -q`
- `python -m pytest -q` -> `254 passed`
- Source GUI smoke across Dashboard, Mods, Server, Activity, Settings, and Help
- Packaged exe smoke launch confirmed v0.7.0 identity and startup

### SHA256

`8DE4A57BEFB68A45BBC62927F80027DF88EDF4B43612FF0DFACF5C86BF4D3250`

### Full Changelog

https://github.com/Vercadi/windrose-mod-manager/compare/v0.6.6...v0.7.0
