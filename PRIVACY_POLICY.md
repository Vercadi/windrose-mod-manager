# Windrose Mod Manager Privacy Policy

Last updated: April 20, 2026

Windrose Mod Manager is a Windows desktop application for managing Windrose mods, server settings, backups, and hosted server connections.

This privacy policy explains what data the app accesses, stores, and transmits.

## Summary

- Windrose Mod Manager does **not** include advertising.
- Windrose Mod Manager does **not** include analytics or telemetry.
- Windrose Mod Manager does **not** sell user data.
- Most app data is stored locally on your device.

## Data the App Accesses

Depending on how you use the app, Windrose Mod Manager may access:

- files and folders you choose for Windrose client/server installs
- mod archive files you import
- Windrose configuration files such as `ServerDescription.json` and `WorldDescription.json`
- local backup files created by the app
- hosted server file locations and credentials that you enter

## Data Stored Locally

When running as a packaged Windows app, Windrose Mod Manager stores its app data under:

- `%LOCALAPPDATA%\\WindroseModDeployer`

This may include:

- app settings and configured paths
- archive library records
- install/manifest state and history
- hosted server profiles
- backup metadata and backup files
- logs
- saved UI and behavior preferences

## Hosted Server Profiles

If you use hosted server features, the app may store:

- host/IP
- port
- username
- password
- authentication mode
- private key file path
- remote server folder paths
- restart command text

This information is stored locally so the app can reconnect to hosted servers you configure.

Important:

- saved hosted credentials are currently stored locally in app configuration files on your device
- the app does **not** currently provide built-in credential encryption
- you are responsible for protecting access to your Windows account and local app data

## Network Connections

Windrose Mod Manager may make network connections in these cases:

### 1. Update Checks

The app can check GitHub Releases for new versions of Windrose Mod Manager.

For this feature, the app contacts:

- `https://api.github.com/repos/Vercadi/windrose-mod-manager/releases/latest`

This request is used only to check whether a newer app version exists.

### 2. Hosted Server Connections

If you configure a hosted server profile, the app may connect to the server you specify using:

- SFTP
- FTP

These connections are used only for the hosted server features you request, such as:

- testing the connection
- listing files
- uploading mod files
- deleting mod files
- reading or writing hosted server configuration files

The app only connects to hosted servers that you configure.

### 3. External Links

If you click links inside the app, your web browser may open external sites such as:

- GitHub
- Nexus Mods
- Ko-fi
- Patreon

## Data Sharing

Windrose Mod Manager does not share your data with the developer except through services you explicitly use.

Examples:

- GitHub may receive standard network/request information when update checks are enabled
- your hosted server provider receives the credentials and file operations needed to connect to the hosted server you configured
- external sites you open in your browser are governed by their own privacy policies

## Data Retention and Deletion

You control the data stored by the app on your device.

You can remove local app data by deleting the app's local data folders, including:

- `%LOCALAPPDATA%\\WindroseModDeployer`

You can also remove hosted profiles, backups, and other app-managed data from inside the app where supported.

## Children

Windrose Mod Manager is not directed to children and does not knowingly collect personal information from children.

## Changes to This Policy

This privacy policy may be updated if the app's data handling changes.

The latest version may be published with future app releases or product pages.

## Contact

For support or privacy questions about Windrose Mod Manager, use one of these channels:

- GitHub issues: `https://github.com/Vercadi/windrose-mod-manager/issues`
- Nexus Mods page: `https://www.nexusmods.com/windrose/mods/29`
