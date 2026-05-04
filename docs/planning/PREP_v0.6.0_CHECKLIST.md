# Windrose Mod Manager - v0.6.0 Prep Checklist

This checklist is for work that should happen before full `v0.6.0` implementation starts.

The goal is to avoid building UI around workflows that are not proven yet, especially UE4SS bundling, RCON, and configurable tweak generation.

## 1. UE4SS Support Prep

### Required before implementation

- [ ] Download the current UE4SS for Windrose archive.
- [ ] Confirm its archive layout:
  - files already under `R5/Binaries/Win64`
  - files under `Binaries/Win64`
  - files at archive root
  - wrapper folder around one of the above
- [ ] Manually install UE4SS to the Windrose client.
- [ ] Manually install UE4SS to the standalone Windrose Dedicated Server.
- [ ] Confirm both launch without fatal errors.
- [ ] Record the exact files/folders UE4SS installs.
- [ ] Confirm whether the runtime marker is `dwmapi.dll`, `dwmappi.dll`, or both.

### Permission / bundling decision

- [ ] Check UE4SS mod page permissions.
- [ ] If you want to bundle UE4SS, ask the author for explicit redistribution permission.
- [ ] If permission is not granted, v0.6 should support user-supplied UE4SS archives only.

Recommended v0.6 default:

- do not bundle UE4SS
- user downloads UE4SS
- user drags archive into manager
- manager installs it correctly

## 2. UE4SS Mod Prep

### Required before implementation

- [ ] Download at least one UE4SS Windrose mod archive.
- [ ] Confirm the archive layout.
- [ ] Manually install it to:
  - client, if relevant
  - dedicated server, if relevant
- [ ] Confirm it works in-game / on server.
- [ ] Record the expected install folder:
  - `R5/Binaries/Win64/ue4ss/Mods/<ModName>`
- [ ] Identify common marker files:
  - `enabled.txt`
  - `settings.ini`
  - `Scripts/main.lua`
  - other mod-specific files

Good first test cases:

- Windrose Source RCON Protocol
- one simple UE4SS mod that does not require RCON

## 3. RCON Prep

### Required before implementation

- [ ] Install UE4SS on a dedicated server.
- [ ] Install the RCON UE4SS mod.
- [ ] Configure its `settings.ini` manually.
- [ ] Confirm which fields exist:
  - port
  - password
  - enabled/disabled
  - bind address, if any
- [ ] Test with an external RCON client.
- [ ] Record exact command behavior:
  - `info`
  - `showplayers`
  - `playerinfo`
  - `kick`
  - `ban`
- [ ] Decide whether v0.6 should include:
  - config editor only
  - connection test
  - read-only player/server info
  - admin commands

Recommended v0.6 default:

- detect RCON mod
- edit known config safely
- show Dashboard status
- defer kick/ban/admin panel unless external testing is solid

## 4. Configurable Overhaul / Tweak Builder Prep

This is separate from UE4SS. Do not block UE4SS support on this unless you want v0.6 to become much larger.

### Required before any build UI

- [ ] Create one manually proven comfort tweak.
- [ ] Create one manually proven inventory or stack tweak.
- [ ] Create one manually proven ship/storage tweak.
- [ ] Combine those three into one generated mod output.
- [ ] Confirm the combined output works in-game.
- [ ] Record the final output files:
  - `.pak`
  - `.utoc`
  - `.ucas`

### Required tweak catalog info

For each supported tweak, record:

- [ ] category
- [ ] asset path
- [ ] property name/path
- [ ] vanilla value
- [ ] test value
- [ ] accepted value range
- [ ] in-game test method
- [ ] whether client/server/both need the generated mod

### Toolchain decision

- [ ] Decide whether v0.6 uses user-supplied `retoc.exe`.
- [ ] Decide whether a later release may bundle `retoc`.
- [ ] If bundling `retoc`, include MIT license notice.
- [ ] Decide how `.usmap` is handled.
- [ ] If using someone else's `.usmap`, get explicit permission before bundling or re-uploading.

Recommended v0.6 default:

- user-supplied `retoc.exe`
- user-supplied `.usmap`
- no bundled `.usmap`
- no public Build button until manual proof + patch-engine spike pass

## 5. Metadata / Version Prep

This is useful before or during `0.5.x`, not necessarily blocked on v0.6.

- [ ] Pick 5 real installed mods and record:
  - Nexus URL
  - Nexus mod ID
  - file ID, if visible
  - version string
  - author/source label
- [ ] Decide how much metadata users should edit manually.
- [ ] Decide if v0.6 should only show local "possible update" hints or attempt upstream checks.

Recommended v0.6 default:

- metadata-first
- notification-only
- no auto-download
- no auto-install

## 6. Hosted Provider Prep

- [ ] Test current hosted FTP/SFTP with one real provider if available.
- [ ] Record exact Host Havoc FTP/SFTP fields if a user provides them.
- [ ] Record exact Indifferent Broccoli FTP fields if a user provides them.
- [ ] Confirm hosted UE4SS is realistic on the provider:
  - file access to `R5/Binaries/Win64`
  - ability to restart from panel
  - Windows/Wine support if UE4SS requires Windows-style runtime files

## 7. Release-Scope Decision Before Coding v0.6

Before starting implementation, decide which lane is the real release goal:

- [ ] UE4SS runtime + UE4SS mod support only
- [ ] UE4SS support + RCON config/status
- [ ] UE4SS support + configurable tweak foundations
- [ ] full UE4SS + RCON + tweak builder

Recommended:

- ship `0.6.0` as UE4SS support + RCON/config foundation
- keep configurable tweak builder as experimental groundwork unless the proof gates pass early

## 8. Minimum Artifacts To Hand To Codex Before v0.6 Coding

Best input package:

- [ ] UE4SS archive layout notes or screenshots
- [ ] one UE4SS mod archive layout example
- [ ] RCON mod `settings.ini` example with secrets removed
- [ ] manual test notes for UE4SS client/dedicated server install
- [ ] optional hosted test notes
- [ ] optional tweak catalog notes if configurable overhaul should advance

## One-Sentence Rule

Do the manual proof for anything that changes game/runtime behavior before building polished UI around it.
