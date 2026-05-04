Windrose Mod Manager v0.6.2

Short Nexus file changelog

- Reduced antivirus/Chrome false-positive triggers introduced by v0.6.1.
- Removed WindrosePlus stop/restart process-control buttons for now.
- Removed the forced `ExecutionPolicy Bypass` flag from WindrosePlus script helpers.
- Kept UE4SS, RCON, WindrosePlus detection/install/config support.
- Normal pak archives are still copied into the manager archive library, but external framework/tool bundles such as UE4SS, RCON, and WindrosePlus are linked from their original location instead of copied into app data.
- Clarified Settings wording for Local Server vs standalone Dedicated Server.
- Dedicated server running detection now also checks `WindroseServer-Win64-Shipping.exe`.

Sticky update

April 26:
v0.6.2 is live.

This is a small hotfix for v0.6.1. It keeps the framework support work, but removes the new process-control pieces that were more likely to trigger antivirus / browser false positives.

What changed in v0.6.2
- Removed WindrosePlus Stop / Restart controls for now.
- Removed the forced PowerShell `ExecutionPolicy Bypass` flag from WindrosePlus install/rebuild helpers.
- Framework/tool archives such as UE4SS, RCON, and WindrosePlus are no longer copied into the manager's app-data archive folder by default.
- Normal pak mod archives still get manager-owned library copies.
- Kept WindrosePlus launch, dashboard, config editing, install, and rebuild support.
- Clarified Settings wording:
  - Local Server = bundled server inside the main Windrose game install
  - Dedicated Server = separate Steam Windrose Dedicated Server app
- Dedicated server running detection now checks both:
  - WindroseServer.exe
  - WindroseServer-Win64-Shipping.exe

Why this update exists
v0.6.1 added WindrosePlus process-control helpers and also copied imported framework archives into the manager app-data archive folder. Those behaviors were user-triggered, but unsigned packaged Python apps plus PowerShell/process-control behavior and copied third-party tool archives can trip antivirus heuristics. v0.6.2 removes the highest-risk parts while keeping the useful framework install/config support.

Important framework notes
- UE4SS, WindrosePlus, and RCON are not bundled with the manager.
- You still import the user-supplied archives yourself.
- WindrosePlus and RCON are server-side tools, not client mods.
- If you need to stop/restart a WindrosePlus server, use the WindrosePlus window/dashboard, Windows process controls, or your normal server workflow for now.
- Keep your downloaded UE4SS/RCON/WindrosePlus archives somewhere available if you want to reinstall them later; the manager will link those framework/tool archives instead of copying them into app data.

Antivirus / VirusTotal note
A few users have reported antivirus/ML detections on the packaged exe. At the moment this still appears to be a false-positive pattern related to the unsigned packaged Python build, not known malicious behavior. The source code is public on GitHub, and release hashes are available if you want to verify the download yourself.
