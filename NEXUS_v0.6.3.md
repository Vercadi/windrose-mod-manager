Windrose Mod Manager v0.6.3

Short Nexus file changelog

- Improved hosted FTP/Nitrado troubleshooting.
- Separate error messages for bad hostname/DNS, FTP timeout/unreachable service, login rejected, wrong protocol, and missing remote folder paths.
- Hosted connection tests now show non-secret diagnostics: protocol, host, port, username, server folder, and overrides.
- Added Copy Diagnostics in Hosted Server Setup.
- Added clearer Nitrado guidance: use FTP Credentials and port 21, not Query/RCON/Game ports.
- Slightly increased FTP connection timeout from 10 seconds to 15 seconds.
- Minor framework wording cleanup around UE4SS source archives.

Sticky update

April 28:
v0.6.3 is live.

This is a small hosted-server diagnostics update. It is mainly for users setting up FTP hosts such as Nitrado.

What changed in v0.6.3
- Better hosted FTP error messages.
- Bad hostname / DNS errors now clearly say the hostname could not be resolved.
- FTP timeout / unreachable server errors now mention firewall, VPN, router/ISP FTP blocking, provider session limits, or provider outage.
- FTP login errors now clearly say username/password was rejected.
- Remote path errors are still separate, so you can tell when the app connected but could not find the configured folder.
- Hosted connection tests now include non-secret diagnostics:
  - protocol
  - host
  - port
  - username
  - server folder
  - overrides
- Added Copy Diagnostics in Hosted Server Setup so users can paste useful connection info without sharing passwords/private keys.
- Hosted Setup now explains Nitrado more clearly:
  - use FTP Credentials
  - FTP port is usually 21
  - Query/RCON/Game ports are not FTP ports

Nitrado note
If you are using Nitrado, use the FTP Credentials section from the Nitrado panel:
- Protocol: FTP
- Host / IP: the FTP hostname, for example ms2084.gamedata.io
- Port: 21
- Username: the FTP username
- Password: the FTP password

Do not use the Query Port, RCON Port, or game port as the FTP port.

If the manager says the FTP service cannot be reached, try the same credentials in WinSCP or FileZilla from the same PC. If those also fail, it is likely network/firewall/VPN/router/ISP/provider-side rather than the manager.

This update does not add FTPS, Nexus downloading, load order, or new framework features. It is a support/diagnostics cleanup release.
