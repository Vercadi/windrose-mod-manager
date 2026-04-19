# Windrose Mod Manager - v0.5.1 Pre-Implementation Audit

## Purpose

This audit captures the current startup and hosted-server seams before `v0.5.1` implementation begins.

The goal is to reduce risk while adding:

- faster startup
- a real Dashboard operations home
- FTP support for real hosted providers without regressing existing SFTP users

## Checkpoint

- Git checkpoint commit created before this pass:
  - `6892e9b` - `Checkpoint v0.5.0 worktree`

## Startup Audit

Current startup flow is centered in `windrose_deployer/ui/app_window.py`:

1. `_init_services()`
   - loads settings
   - reconciles paths
   - initializes manifest, profile, recovery, and hosted services
2. `_build_ui()`
   - builds Dashboard, Mods, Server, Activity, Settings, Help
3. `_initial_load()`
   - refreshes Mods, Server, Dashboard, Help, and Activity immediately
   - schedules update check
   - schedules welcome dialog

Risk:

- the app is still doing too much before the first interaction
- tab refresh work is eager instead of lazy
- path reconciliation still performs broad discovery every launch

Mitigation added now:

- baseline startup timing logs in `app_window.py`
- path discovery timing logs in `discovery.py`

## Hosted Architecture Audit

Current hosted transport is SFTP-first in the core layer.

### Core seams

- `windrose_deployer/core/remote_deployer.py`
  - defaults to `SftpProvider`
  - restart relies on `provider.execute(...)`
- `windrose_deployer/core/remote_config_service.py`
  - defaults to `SftpProvider`
  - writes remote backup source URIs as `sftp://...`
  - restore parsing only accepts `sftp://...`
- `windrose_deployer/core/remote_provider.py`
  - already provides the correct abstraction boundary for adding an FTP backend

### Model / storage seams

- `windrose_deployer/models/remote_profile.py`
  - no `protocol` field yet
  - current auth model is `password` or `key`
  - current model includes `restart_command`
- `windrose_deployer/core/remote_profile_store.py`
  - will need backward-compatible defaulting when `protocol` is introduced

### UI seams

- `windrose_deployer/ui/tabs/server_tab.py`
  - hosted setup currently assumes SSH/SFTP concepts in several places
  - restart-command language is currently visible in the hosted workflow

## Provider Findings

### Host Havoc

Official docs show mixed behavior:

- some panels expose `FTP Info`
- some panels expose `SFTP Info`

Implementation rule:

- Host Havoc support must allow explicit protocol choice and preserve explicit panel ports

### Indifferent Broccoli

Official docs describe plain FTP:

- host = server IP / FTP hostname
- username/password from the provider panel
- port `21`

Implementation rule:

- FTP is a must-have if we want first-class support for this provider

## Locked Scope Boundaries

- `sftp`: yes
- `ftp`: yes
- `ftps`: not in the critical path
- FTP restart / remote command execution: no
- no provider autodetection in this pass

## Compatibility Fixtures Prepared

Sanitized fixtures were added under `tests/fixtures/compat/` for the current live data shape:

- `settings.current.json`
- `remote_profiles.current.sftp.json`
- `app_state.current.json`
- `app_state.v1.legacy.json`
- `backup_records.current.remote.json`

These fixtures exist to protect:

- settings loading
- remote profile loading with no protocol field
- manifest/app-state compatibility
- hosted backup restore compatibility for old `sftp://...` records
