# Windrose Mod Manager - v0.6.4 Implementation Plan

## Release Goal

`v0.6.4` should be a stabilization and support-quality release after the hosted/framework work in `v0.6.0` through `v0.6.3`.

The goal is not to add another major feature. The goal is to make support easier, reduce false confusion in the UI, and make the app better at explaining its current state when users report issues.

This release should improve:

- hosted setup troubleshooting
- framework status consistency
- support bundle / diagnostics sharing
- stale dashboard or compare state after installs/uninstalls
- user-facing wording around server-only framework mods

## Non-Goals

Do not implement:

- load-order management
- Nexus update checks/downloads
- `retoc` integration
- FTPS
- RCON admin commands
- generic remote file browser
- WindrosePlus dashboard clone
- broad visual rewrite
- configurable overhaul / generated pak building

Keep this release low-risk and support-driven.

---

## Must-Have

### 1. Export Support Info

Add a support export action, ideally from `Help` and/or `Activity`.

It should create a small zip or copied text payload containing redacted diagnostics.

Include:

- app version
- Python/frozen build state where available
- configured target availability summary:
  - client configured / missing
  - local server configured / missing
  - dedicated server configured / missing
  - hosted profile protocol/host/port only
- recent log tail
- recent activity/history summary
- manifest counts
- framework state summary:
  - UE4SS
  - RCON
  - WindrosePlus
- hosted connection diagnostics from the last test if available

Redact:

- hosted passwords
- private key contents
- API keys/tokens if any appear later
- Windows username in full paths where practical

Acceptance:

- A user can attach one support file or paste one support text block without exposing credentials.
- The support export is useful for Nexus/GitHub comments where users only say "it does not work."

### 2. Hosted Setup State Audit

Polish hosted setup after the v0.6.3 diagnostics changes.

Implement:

- trim hidden whitespace from host/username/path fields before tests/saves
- show normalized host/port/protocol before testing
- keep FTP/SFTP wording separate and clear
- make "connected but path missing" visually distinct from "could not connect"
- include a "Try with Server Folder = ." hint only when login succeeded but derived paths fail
- keep Nitrado wording focused on FTP Credentials and port 21

Acceptance:

- Common screenshots should be enough to tell whether the issue is hostname, port, login, or path.
- Users are less likely to confuse game/query/RCON ports with FTP.

### 3. Framework Status Consistency

Audit framework detection and refresh behavior.

Focus areas:

- UE4SS runtime status after uninstall/reinstall
- UE4SS mod status when runtime is missing
- RCON status when only `version.dll` exists but generated `windrosercon/settings.ini` does not yet exist
- WindrosePlus status after running install/rebuild/start dashboard actions
- Dashboard refresh after framework install/uninstall/actions
- Server Frameworks screen refresh after running framework actions

Acceptance:

- Dashboard and Frameworks screen agree after pressing Refresh.
- Framework states do not imply "fully installed" when only partial markers exist.
- RCON wording explains that `settings.ini` is generated after first server start.

### 4. Compare / Sync Wording Cleanup

Server-only framework mods should not produce confusing client-sync expectations.

Implement:

- mark UE4SS/RCON/WindrosePlus packages as framework/server tooling where detected
- in compare/sync review, explain server-only framework differences separately
- do not offer client sync for packages that are intentionally server-only
- keep normal gameplay pak mods unaffected

Acceptance:

- Users understand why WindrosePlus/RCON may exist on server only.
- Compare does not imply every server-side framework package should be copied to client.

### 5. Activity Performance Guardrails

Keep the Activity tab lightweight for users with long histories.

Implement or verify:

- default visible activity count is capped
- add "Show more" or equivalent if not already present
- avoid rebuilding the full timeline when switching tabs unless data changed
- avoid expensive raw backup scans on every tab open

Acceptance:

- Activity opens quickly even with many history records/backups.

---

## Nice-To-Have

Only include if low-risk:

- Copy Support Info button that copies a text summary without creating a zip
- last hosted test timestamp in Hosted Setup
- "Open log folder" action near support export
- small Help tab section explaining:
  - Client vs Local Server vs Dedicated Server vs Hosted Server
  - FTP/SFTP setup basics
  - server-only framework mods

---

## Tests

Add or update tests for:

- support diagnostics redacts passwords and private key data
- support diagnostics includes version/target/profile summary
- hosted field normalization trims whitespace without changing explicit ports
- framework partial states are classified correctly
- compare/sync excludes server-only framework packages from client sync actions
- Activity refresh uses a capped/default visible count where practical

Run:

```powershell
python -m compileall windrose_deployer -q
python -m pytest -q
git diff --check
```

---

## Manual Smoke Checklist

- Export support info and verify no password/private key content is present.
- Create hosted FTP profile with extra spaces in host/username/path and verify test uses normalized values.
- Test hosted profile with wrong path after successful login and verify path-specific guidance.
- Install/uninstall UE4SS runtime and verify Dashboard + Frameworks screen agree.
- Install RCON `version.dll` archive, start server once if available, and verify generated settings wording.
- Install WindrosePlus, run install/rebuild/dashboard actions, and verify status updates after Refresh.
- Run compare where WindrosePlus/RCON exists only on server and verify it is explained as server-side/framework tooling.
- Open Activity with a large history and confirm it does not render the full list by default.

---

## Release Notes Shape

Keep public wording short:

- added redacted support info export
- improved hosted setup normalization and path guidance
- cleaned up framework status/refresh consistency
- clearer compare wording for server-only framework packages
- Activity tab performance guardrails

