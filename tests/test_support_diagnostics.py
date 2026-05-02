from pathlib import Path

from windrose_deployer.core.framework_state_service import FrameworkStateService
from windrose_deployer.core.manifest_store import ManifestStore
from windrose_deployer.core.remote_profile_store import RemoteProfileStore
from windrose_deployer.core.support_diagnostics import SupportDiagnosticsService, redact_sensitive_text
from windrose_deployer.models.app_paths import AppPaths
from windrose_deployer.models.deployment_record import DeploymentRecord
from windrose_deployer.models.mod_install import ModInstall
from windrose_deployer.models.remote_profile import RemoteProfile


def test_redact_sensitive_text_removes_secret_fields_and_user_paths():
    raw = (
        "Password=abc123\n"
        "api_key: token-value\n"
        "C:\\Users\\jonte\\AppData\\Local\\WindroseModDeployer\\data\n"
        "C:/Users/jonte/AppData/Local/WindroseModDeployer/data"
    )

    redacted = redact_sensitive_text(raw, secrets=["abc123"])

    assert "abc123" not in redacted
    assert "token-value" not in redacted
    assert "C:\\Users\\jonte" not in redacted
    assert "C:/Users/jonte" not in redacted
    assert "<redacted>" in redacted
    assert "C:\\Users\\<user>" in redacted
    assert "C:/Users/<user>" in redacted


def test_support_report_includes_summary_fields_and_redacts_profile_secrets(tmp_path):
    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups"
    data_dir.mkdir()
    backup_root.mkdir()
    (data_dir / "deployer.log").write_text(
        "line one\nPassword=should-not-leak\nC:\\Users\\jonte\\secret\n",
        encoding="utf-8",
    )
    client_root = tmp_path / "Windrose"
    client_root.mkdir()
    paths = AppPaths(
        client_root=client_root,
        data_dir=data_dir,
        backup_dir=backup_root,
    )
    manifest = ManifestStore(data_dir)
    manifest.add_mod(
        ModInstall(
            mod_id="m1",
            display_name="Mining",
            source_archive="Mining.zip",
            targets=["client"],
            installed_files=[str(client_root / "R5" / "Content" / "Paks" / "~mods" / "Mining_P.pak")],
        )
    )
    manifest.add_record(
        DeploymentRecord(
            mod_id="m1",
            action="install",
            target="client",
            display_name="Mining",
        )
    )
    remote_profiles = RemoteProfileStore(data_dir)
    remote_profiles.upsert(
        RemoteProfile(
            profile_id="p1",
            name="Nitrado",
            protocol="ftp",
            host="ms2084.gamedata.io",
            port=21,
            username="server_user",
            password="ftp-password",
            private_key_path="C:/Users/jonte/.ssh/id_rsa",
            remote_root_dir=".",
        )
    )

    report = SupportDiagnosticsService().build_report(
        paths=paths,
        manifest=manifest,
        remote_profiles=remote_profiles,
        framework_state=FrameworkStateService(),
        data_dir=data_dir,
        backup_root=backup_root,
        last_hosted_diagnostics="Last result: Password=ftp-password",
    )

    assert "Windrose Mod Manager support info" in report
    assert "App:" in report
    assert "Client: configured" in report
    assert "Nitrado: FTP ms2084.gamedata.io:21 as server_user" in report
    assert "Active installs: 1 / 1" in report
    assert "Recent activity: 1 shown" in report
    assert "ftp-password" not in report
    assert "id_rsa" not in report
    assert "C:\\Users\\jonte" not in report
