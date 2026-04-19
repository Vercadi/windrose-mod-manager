# Windrose Mod Manager - Roadmap

## v0.2.0 - Trust Baseline (current)

The first public build people will keep using. Safety invariants and identity must be correct before persistent user data exists in the wild.

### Safety & Identity
- [x] Uninstall restores originals from backup (not just delete)
- [x] Reinstall preflight validation (don't destroy working install before confirming replacement)
- [x] Accurate Install All counting (succeeded/failed/skipped)
- [x] UUID-based mod identity (no name collisions, stable across renames)
- [x] Manifest schema versioning with forward migration (v1 name-based ids auto-migrate to v2 UUIDs)
- [x] Pre-migration manifest backup (`app_state.v1.bak.json` created before any schema rewrite)
- [x] Manifest collision guard (safety net even with UUIDs)

### Safety Regression Tests
- [x] Overwrite install then uninstall restores original file content
- [x] Duplicate display names get different mod IDs
- [x] v1 manifests migrate to UUID-based v2 schema
- [x] Migration creates backup copy of old manifest before rewriting
- [x] Invalid plans report as failures, not successes

### Features
- [x] Archive library (persistent sidebar, survives restarts)
- [x] Quick install (double-click or right-click)
- [x] Uninstall from Mods tab (right-click or detail panel)
- [x] Installed mod count badge
- [x] Multi-mod drag/drop and browse
- [x] Start Game / Start Server buttons with combined launcher
- [x] About tab with version, author, links
- [x] Update check (GitHub Releases API, startup + manual)
- [x] Uninstall All button with confirmation
- [x] Installed tab search/filter
- [x] Reinstall option (with preflight)

### Release Gates
- [ ] `pytest` green (all safety + unit tests pass)
- [ ] Migration tested on a real pre-v0.2.0 `app_state.json` with name-based mod IDs
- [ ] Packaged-build smoke test: install, uninstall, reinstall cycle works correctly from the PyInstaller `.exe` (path behavior often changes once packaged)

---

## v0.2.1 - Hotfix & State Consistency

Small release focused on fixing shipped correctness issues before remote/rented-server support lands.

### Release blockers
- [x] Disabled mods that overwrote files still restore originals on uninstall
- [x] Restore backup writes to the currently configured `ServerDescription.json`, not a stale path from backup metadata
- [x] Mods tab supports multiple installs from the same archive path without ambiguous badges/uninstall actions
- [x] Changing Backup Directory takes effect immediately, or the UI explicitly requires restart before claiming success

### Regression coverage
- [x] Disable -> uninstall -> original file restored after overwrite
- [x] Server config restore targets the active configured path only
- [x] Same archive installed to multiple targets remains representable in Mods tab
- [x] Backup-directory change is honored by live services

### UX follow-up
- [x] Grouped conflict display (by mod, file count, target path)
- [x] Conservative variant detection (flag uncertain cases for user decision instead of guessing)
- [ ] Better error messages for common failure modes
- [ ] UI polish based on first user reports

---

## v0.3.0 - Remote Server & Recovery

The next major feature set: make the tool useful for rented servers while strengthening recovery and verification.

### Product direction
- [x] Remote/rented-server support is a first-class feature
- [x] Managed remote deployment uses **SFTP/SSH first**
- [ ] FTPS can be added if hosts require it
- [x] Plain FTP is deferred unless a host forces it, because it is the weakest protocol option

### Remote server MVP
- [x] Saved remote connection profiles
- [x] Connection test and validation before any upload
- [x] Configurable remote mods directory
- [x] Remote install uses a real deployment plan, not raw archive dumping
- [x] Variant-aware remote install (only the selected variant is uploaded)
- [x] Remote upload preserves only planned files/paths
- [x] Remote file listing / path verification
- [x] Clear post-upload summary (succeeded/failed/skipped with reasons)
- [x] Restart guidance or optional restart action after deploy

### Remote architecture rules
- [x] Introduce a small remote provider abstraction (`RemoteProvider`)
- [x] Implement `SftpProvider` first
- [x] Keep archive path safety rules for remote deployment too
- [x] No arbitrary remote shell/command console in the MVP
- [x] No fake "supports every rented host" claim until multiple hosts are validated

### Recovery & verification
- [x] Verify install (check manifest against actual files on disk, report drift)
- [x] Repair install (re-extract missing files from archive if archive is still available)
- [x] Better batch action summaries (succeeded/failed/skipped with reasons)
- [x] Drift detection on startup (warn if files changed outside the manager)

### Test matrix
- [x] Remote install uses deployment plan output, not raw archive contents
- [x] Remote install uploads only the selected variant
- [x] Unsafe archive paths are rejected in remote workflow too
- [x] Remote result summaries count succeeded/failed/skipped correctly
- [ ] End-to-end SFTP smoke test against a rented-server-like target

---

## v0.4.0 - Server Differentiation

This is where the product becomes more useful than generic mod managers for Windrose server operators.

### Server-safe apply
- [ ] Apply workflow: validate mod set, deploy, prompt for server restart, verify post-restart
- [ ] Running-server detection and warning before writes
- [ ] Apply guidance: surface which changes need a server restart vs. which are hot-loadable (if any)

### Client/server sync validation
- [ ] Define source of truth: manifest is authoritative, on-disk scan is verification
- [ ] Detect mismatched mod states between client and server targets
- [ ] Surface sync status clearly (which mods are client-only, server-only, or both)

### WorldDescription.json workflows
- [ ] Per-world discovery (enumerate worlds under SaveProfiles, show active world from ServerDescription.json)
- [ ] Running-server save behavior is explicit (warn/block/allow depending on what Windrose actually supports)
- [ ] Backup diff/restore (show what changed between backups, restore specific versions)
- [ ] Apply guidance (which settings need world restart vs. server restart)

---

## v0.5.x - Server Operations & Parity

Detailed working plan lives in `PLAN_v0.5.x.md`.
Detailed implementation brief lives in `IMPLEMENTATION_v0.5.0.md`.

High-level direction:
- [ ] Server dashboard with clearer local/dedicated/hosted status
- [ ] Metadata/version awareness foundation
- [ ] Bundle-aware archive/applied mod cards
- [ ] Better inspect surface for complex archives
- [ ] Backups and activity/logs become first-class workflows
- [ ] Framework/dependency awareness
- [ ] Narrow, preview-first Profiles

---

## v1.0 - Framework Extraction (future)

**Rule: don't build a framework until there is a second game. But keep the current code ready for extraction.**

Second adapter must prove the abstraction without changing Windrose behavior. The extraction is only valid if the Windrose adapter works identically before and after.

Current design seams to maintain:
- Windrose-specific discovery/config logic is grouped (not scattered)
- Path assumptions stay out of generic install/manifest/backup code
- Archive/install/manifest/backup logic is game-agnostic
- Plugin-style adapter model is the extraction target, not the current implementation

When a second UE game needs mod management, extract the generic core into a shared framework and keep Windrose as the first adapter.

---

## Design Principles

1. **The app should always be able to answer**: "what changed, what was replaced, and how do I get back to the previous state?"
2. **Don't ship persistent public state with weak identity semantics.** Fix identity before the first real release, not after.
3. **Design for extraction, don't perform extraction yet.** Light seams now, full plugin architecture later.
4. **Safety over features.** Every release must pass its safety regression suite.
