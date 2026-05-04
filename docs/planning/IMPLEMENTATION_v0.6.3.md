# Windrose Mod Manager - v0.6.3 Implementation Plan

## Release Goal

`v0.6.3` is a small diagnostics and support-cleanup release.

The goal is to reduce support friction after the hosted FTP and framework releases, especially for Nitrado users, without adding new major features.

This release should make the app better at answering:

- Did the hostname resolve?
- Did the FTP port answer?
- Was login rejected?
- Did the remote folder/path check fail?
- Is the user using game/query/RCON ports instead of FTP/SFTP ports?
- Is framework state clear and stable after the v0.6.0-v0.6.2 changes?

## Non-Goals

Do not implement:

- new framework features
- WindrosePlus stop/restart process control
- FTPS
- Nexus update/download support
- load-order management
- profile/loadout overhaul
- generic remote file browser
- provider-specific API integration
- RCON admin commands
- broad UI rewrite

Keep this release narrow and support-driven.

---

## Must-Have

### 1. Hosted FTP Error Classification

Improve hosted connection errors so different failures produce different messages.

Cases to distinguish:

- DNS / bad hostname:
  - examples: `[Errno 11001] getaddrinfo failed`, `Name or service not known`, `nodename nor servname`
  - message should say the hostname could not be resolved and ask the user to check for typos or hidden spaces

- FTP port unreachable / timeout:
  - examples: `timed out`, `connection refused`, `connection reset`
  - message should say the FTP service could not be reached from this PC
  - mention firewall, VPN, router/ISP FTP blocking, Nitrado session limits, or provider outage

- FTP login rejected:
  - examples: `530`, `Login incorrect`, `Not logged in`
  - message should say username/password was rejected

- Wrong protocol:
  - examples: FTP selected but server responds like SSH/SFTP, or SFTP selected but SSH banner fails against FTP
  - message should say selected protocol likely does not match provider details

- Remote path/folder missing:
  - keep existing path-specific errors, but make clear this happens after successful connection/login

Acceptance:

- A Nitrado user with a typo like `ms2048.gamedata.io` instead of `ms2084.gamedata.io` sees a hostname/DNS error, not a generic protocol mismatch.
- A user blocked by firewall/VPN sees a network reachability message, not “wrong protocol.”
- Login and folder-path failures remain separate.

### 2. Connection Test Diagnostics Summary

After `Test Connection`, include a short resolved-target summary in success and failure messages.

Include:

- protocol
- host
- port
- username
- server folder if set
- mods override if set

Never include password or private key content.

Example:

```text
Tried FTP ms2084.gamedata.io:21 as ni9352260_103554.
```

Acceptance:

- Support screenshots show enough non-secret info to spot wrong host/port/protocol immediately.

### 3. Nitrado-Focused Hosted Setup Help

Add clearer text in Hosted Setup for FTP providers.

Must clarify:

- use `FTP Credentials`, not query/game/RCON ports
- FTP port is usually `21`
- Nitrado `Query Port` / `RCON Port` are not the FTP port
- Host field should contain only the hostname, for example `ms2084.gamedata.io`
- no `ftp://` prefix is required, though the normalizer may still tolerate it

Acceptance:

- The UI makes it harder to confuse Nitrado game/query/RCON ports with FTP port.

### 4. Diagnostic Copy Button

Add a small way to copy hosted diagnostics after a connection test.

Minimum acceptable version:

- a `Copy Diagnostics` button in Hosted Setup after a failed/successful test
- copies non-secret connection context and last result text to clipboard

Do not include:

- password
- private key path contents
- full local user paths unless already visible in the profile fields

Acceptance:

- User can paste useful diagnostics into Nexus/GitHub/Discord without revealing secrets.

### 5. Framework Support Stability Cleanup

Do a small audit of the v0.6.0-v0.6.2 framework surfaces.

Check:

- UE4SS runtime state wording
- UE4SS mod state wording
- RCON server-only wording
- WindrosePlus server-only wording
- Dashboard framework state after install/uninstall/manual refresh
- no removed WindrosePlus stop/restart controls still referenced in docs/UI

Acceptance:

- Framework support feels stable and consistent, but no new feature scope is added.

---

## Nice-To-Have

Only include if low-risk:

- slightly longer FTP connect timeout, or one retry before failing
- show “Last hosted test” timestamp in Hosted Setup
- add a short “Try WinSCP/FileZilla from the same PC” hint for network/timeout errors
- include `Test-NetConnection <host> -Port <port>` in the copied diagnostics guidance

---

## Tests

Add or update tests for:

- DNS/getaddrinfo FTP errors map to hostname message
- FTP timeout maps to network/firewall/VPN message
- FTP auth failure maps to login message
- wrong-protocol errors still map to protocol mismatch
- diagnostics summary redacts passwords
- Nitrado helper copy exists in Hosted Setup strings where practical

Run:

```powershell
python -m compileall windrose_deployer -q
python -m pytest -q
git diff --check
```

---

## Manual Smoke Checklist

- Create FTP hosted profile with correct host/port and wrong password; confirm login error.
- Create FTP hosted profile with typo hostname; confirm hostname/DNS error.
- Create FTP hosted profile with blocked/unreachable host or wrong port; confirm network/timeout error.
- Confirm `Test Connection` message shows protocol/host/port/username but not password.
- Confirm `Copy Diagnostics` does not include password/private key content.
- Confirm Nitrado help text mentions FTP Credentials and port 21.
- Confirm Hosted setup still works for existing SFTP profiles.
- Confirm Dashboard framework state still refreshes after manual refresh.

---

## Release Notes Shape

Keep Nexus/GitHub wording short:

- improved Nitrado/FTP connection diagnostics
- clearer hosted setup guidance
- safer copyable diagnostics for support
- minor framework wording/status cleanup

