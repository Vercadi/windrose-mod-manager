Windrose Mod Manager v0.7.0

Short Nexus file changelog

- Added external/host-managed UE4SS support.
- Hosted profiles can mark UE4SS as managed by the host/provider.
- UE4SS-dependent mods can now be installed/uploaded without replacing a working external UE4SS runtime.
- This helps hosted users who need a provider-installed or experimental GitHub UE4SS build instead of the Nexus UE4SS runtime.
- Dashboard starts faster and only builds the Dashboard at startup.
- Mods, Server, Activity, Settings, and Help now lazy-load on first use.
- Fixed blank lazy tabs and early v0.7 lazy-load crashes.
- Fixed Mods tab redraw/layout loop that could cause loading spam or crashes.
- Fixed clipped text in Mods and Server panes.
- Reduced UI hitches by avoiding Server auto-prewarm, removing duplicate Mods first-load work, using cached Server process checks, and delaying heavy drift scans.

Sticky update

v0.7.0 is live.

This update is mainly for hosted-server compatibility, UE4SS-dependent mods, and stability/performance fixes.

What changed in v0.7.0
- New external/host-managed UE4SS option.
- Use this when your host/provider, manual setup, or Bisect support already installed a working UE4SS runtime.
- The manager will allow UE4SS mods while leaving that runtime alone.
- Hosted profiles now show when UE4SS is external.
- Hosted upload warns softly when UE4SS is external instead of trying to replace it.
- Dashboard startup is much faster.
- Non-Dashboard tabs are lazy-loaded.
- Lazy tabs now show placeholders instead of blank pages.
- Fixed crashes from the first v0.7 lazy-tab test builds.
- Fixed Mods tab loading/redraw spam that could end in a crash.
- Fixed several clipped text areas in Mods and Server.
- Reduced visible lag during startup and tab refreshes.

Important UE4SS note
- This does not make a broken UE4SS runtime work by itself.
- If the Nexus UE4SS runtime does not launch for your host, keep using the runtime your host/provider helped you install.
- Mark UE4SS as external/host-managed, then use this manager to install/upload other UE4SS mods.

Recommended hosted setup
1. Open Server.
2. Edit or create your hosted profile.
3. Enable "UE4SS is managed by host/provider".
4. Save the profile.
5. Install/upload your UE4SS-dependent mod.

Known follow-up
- Server first open can still take a moment because that tab is built on first selection. It no longer slows app startup.
