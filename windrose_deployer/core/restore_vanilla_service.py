"""Preview and execute local restore-to-vanilla cleanup plans."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from ..models.app_paths import AppPaths
from ..models.mod_install import ModInstall, expand_target_values, summarize_target_values, target_value_label
from ..utils.filesystem import safe_delete
from .backup_manager import BackupManager
from .installer import Installer
from .live_mod_inventory import bundle_live_file_names, snapshot_live_mods_folder
from .manifest_store import ManifestStore

log = logging.getLogger(__name__)

RESTORE_VANILLA_TARGETS = ("client", "server", "dedicated_server")
RESTORE_VANILLA_CATEGORY = "restore_vanilla"


@dataclass(frozen=True)
class RestoreVanillaItem:
    label: str
    detail: str = ""
    paths: tuple[Path, ...] = ()
    mod: ModInstall | None = None


@dataclass(frozen=True)
class RestoreVanillaPlan:
    target: str
    target_label: str
    root: Path | None
    mods_dir: Path | None
    managed_mods: tuple[RestoreVanillaItem, ...] = ()
    managed_review: tuple[RestoreVanillaItem, ...] = ()
    unmanaged_files: tuple[RestoreVanillaItem, ...] = ()
    framework_files: tuple[RestoreVanillaItem, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def has_actions(self) -> bool:
        return bool(self.managed_mods or self.unmanaged_files or self.framework_files)


@dataclass(frozen=True)
class RestoreVanillaResult:
    removed_managed: int = 0
    removed_unmanaged: int = 0
    removed_frameworks: int = 0
    backups_created: int = 0
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class RestoreVanillaService:
    """Build and execute local-only cleanup plans for one selected target."""

    def __init__(
        self,
        paths: AppPaths,
        manifest: ManifestStore,
        installer: Installer,
        backup: BackupManager,
    ):
        self.paths = paths
        self.manifest = manifest
        self.installer = installer
        self.backup = backup

    def build_plan(self, target: str) -> RestoreVanillaPlan:
        target = _normalize_target(target)
        root, mods_dir = self._target_paths(target)
        target_label = target_value_label(target)
        warnings: list[str] = []

        if target == "hosted":
            raise ValueError("Hosted restore-to-vanilla is not supported yet.")
        if target not in RESTORE_VANILLA_TARGETS:
            raise ValueError(f"Unsupported restore target: {target}")

        if root is None:
            return RestoreVanillaPlan(
                target=target,
                target_label=target_label,
                root=None,
                mods_dir=mods_dir,
                warnings=(f"{target_label} path is not configured in Settings.",),
            )

        mods = self.manifest.list_mods()
        managed, review = self._plan_managed_mods(target, mods)
        unmanaged = self._plan_unmanaged_files(target, mods, mods_dir)
        frameworks = self._plan_framework_files(root)

        if mods_dir is None:
            warnings.append(f"{target_label} ~mods folder is not configured.")
        elif not mods_dir.exists():
            warnings.append(f"{target_label} ~mods folder was not found: {mods_dir}")

        return RestoreVanillaPlan(
            target=target,
            target_label=target_label,
            root=root,
            mods_dir=mods_dir,
            managed_mods=tuple(managed),
            managed_review=tuple(review),
            unmanaged_files=tuple(unmanaged),
            framework_files=tuple(frameworks),
            warnings=tuple(warnings),
        )

    def execute_plan(
        self,
        plan: RestoreVanillaPlan,
        *,
        include_managed: bool,
        include_unmanaged: bool,
        include_frameworks: bool,
    ) -> RestoreVanillaResult:
        if plan.root is None:
            return RestoreVanillaResult(errors=tuple(plan.warnings or ("Target is not configured.",)))
        if plan.target == "hosted":
            return RestoreVanillaResult(errors=("Hosted restore-to-vanilla is not supported yet.",))

        removed_managed = 0
        removed_unmanaged = 0
        removed_frameworks = 0
        backups_created = 0
        warnings: list[str] = []
        errors: list[str] = []

        if include_managed:
            for item in plan.managed_mods:
                if item.mod is None:
                    continue
                try:
                    record = self.installer.uninstall(item.mod)
                    self.manifest.add_record(record)
                    self.manifest.remove_mod(item.mod.mod_id)
                    removed_managed += 1
                except Exception as exc:
                    log.error("Restore Vanilla managed uninstall failed for %s: %s", item.label, exc)
                    errors.append(f"{item.label}: {exc}")

        cleanup_items: list[tuple[str, RestoreVanillaItem]] = []
        if include_unmanaged:
            cleanup_items.extend(("unmanaged", item) for item in plan.unmanaged_files)
        if include_frameworks:
            cleanup_items.extend(("framework", item) for item in plan.framework_files)

        for category, item in cleanup_items:
            existing_paths = _dedupe_existing_paths(item.paths, root=plan.root)
            if not existing_paths:
                continue
            try:
                for path in existing_paths:
                    record = _backup_path(self.backup, path, item.label)
                    if record is not None:
                        backups_created += 1
                for path in existing_paths:
                    if path.exists() and not safe_delete(path):
                        errors.append(f"Could not remove {path}")
                if category == "unmanaged":
                    removed_unmanaged += 1
                else:
                    removed_frameworks += 1
            except Exception as exc:
                log.error("Restore Vanilla %s cleanup failed for %s: %s", category, item.label, exc)
                errors.append(f"{item.label}: {exc}")

        if include_managed and plan.managed_review:
            warnings.append(f"{len(plan.managed_review)} multi-target managed mod(s) were left for manual review.")

        return RestoreVanillaResult(
            removed_managed=removed_managed,
            removed_unmanaged=removed_unmanaged,
            removed_frameworks=removed_frameworks,
            backups_created=backups_created,
            warnings=tuple(warnings),
            errors=tuple(errors),
        )

    def _target_paths(self, target: str) -> tuple[Path | None, Path | None]:
        if target == "client":
            return self.paths.client_root, self.paths.client_mods
        if target == "server":
            return self.paths.server_root, self.paths.server_mods
        if target == "dedicated_server":
            return self.paths.dedicated_server_root, self.paths.dedicated_server_mods
        return None, None

    def _plan_managed_mods(self, target: str, mods: Iterable[ModInstall]) -> tuple[list[RestoreVanillaItem], list[RestoreVanillaItem]]:
        managed: list[RestoreVanillaItem] = []
        review: list[RestoreVanillaItem] = []
        for mod in mods:
            targets = expand_target_values(mod.targets)
            if target not in targets:
                continue
            item = RestoreVanillaItem(
                label=mod.display_name,
                detail=f"{len(mod.installed_files)} tracked file(s) | {summarize_target_values(mod.targets)}",
                paths=tuple(Path(path) for path in mod.installed_files),
                mod=mod,
            )
            if targets == {target}:
                managed.append(item)
            else:
                review.append(item)
        return managed, review

    def _plan_unmanaged_files(
        self,
        target: str,
        mods: Sequence[ModInstall],
        mods_dir: Path | None,
    ) -> list[RestoreVanillaItem]:
        snapshot = snapshot_live_mods_folder(mods_dir, mods, target=target)
        if not snapshot.exists or snapshot.folder is None:
            return []
        items: list[RestoreVanillaItem] = []
        for bundle in bundle_live_file_names(snapshot.unmanaged_files):
            paths = tuple(snapshot.folder / name for name in bundle.file_names)
            detail = (
                bundle.file_names[0]
                if bundle.file_count == 1
                else f"{bundle.file_names[0]} (+{bundle.file_count - 1} companion file(s))"
            )
            items.append(RestoreVanillaItem(label=bundle.display_name, detail=detail, paths=paths))
        return items

    def _plan_framework_files(self, root: Path) -> list[RestoreVanillaItem]:
        win64 = root / "R5" / "Binaries" / "Win64"
        paks = root / "R5" / "Content" / "Paks"
        mods_paks = paks / "~mods"

        ue4ss_paths = [
            win64 / "dwmapi.dll",
            win64 / "dwmappi.dll",
            win64 / "xinput1_3.dll",
            win64 / "UE4SS.dll",
            win64 / "UE4SS-settings.ini",
            win64 / "ue4ss",
        ]
        rcon_paths = [
            win64 / "version.dll",
            win64 / "windrosercon",
            win64 / "ue4ss" / "Mods" / "WindroseRCON",
        ]
        windrose_plus_paths = [
            root / "WindrosePlus",
            root / "windrose_plus",
            root / "StartWindrosePlusServer.bat",
            root / "windrose_plus.json",
            root / "windrose_plus.ini",
            root / "windrose_plus.food.ini",
            root / "windrose_plus.weapons.ini",
            root / "windrose_plus.gear.ini",
            root / "windrose_plus.entities.ini",
            win64 / "ue4ss" / "Mods" / "WindrosePlus",
        ]
        for folder in (paks, mods_paks):
            for stem in ("WindrosePlus_Multipliers_P", "WindrosePlus_CurveTables_P"):
                for suffix in (".pak", ".utoc", ".ucas"):
                    windrose_plus_paths.append(folder / f"{stem}{suffix}")

        items = [
            RestoreVanillaItem(
                label="UE4SS runtime/files",
                detail="Known UE4SS loader/runtime files and ue4ss folder.",
                paths=tuple(path for path in ue4ss_paths if path.exists()),
            ),
            RestoreVanillaItem(
                label="WindroseRCON files",
                detail="Known server-side RCON files only.",
                paths=tuple(path for path in rcon_paths if path.exists()),
            ),
            RestoreVanillaItem(
                label="WindrosePlus files",
                detail="Known WindrosePlus package, config, launcher, and generated PAK files.",
                paths=tuple(path for path in windrose_plus_paths if path.exists()),
            ),
        ]
        return [item for item in items if item.paths]


def _normalize_target(target: str) -> str:
    normalized = (target or "").strip().lower()
    aliases = {
        "local": "server",
        "local_server": "server",
        "dedicated": "dedicated_server",
        "dedicated server": "dedicated_server",
        "hosted_server": "hosted",
    }
    return aliases.get(normalized, normalized)


def _backup_path(backup: BackupManager, path: Path, label: str):
    description = f"Restore Vanilla backup: {label}"
    if path.is_dir():
        return backup.backup_directory(path, category=RESTORE_VANILLA_CATEGORY, description=description)
    if path.is_file():
        return backup.backup_file(path, category=RESTORE_VANILLA_CATEGORY, description=description)
    return None


def _dedupe_existing_paths(paths: Iterable[Path], *, root: Path) -> list[Path]:
    existing = [_resolve(path) for path in paths if path.exists() and _is_under_root(path, root)]
    existing.sort(key=lambda path: (len(path.parts), str(path).lower()))
    result: list[Path] = []
    for path in existing:
        if any(_is_same_or_child(path, parent) for parent in result):
            continue
        result.append(path)
    return result


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        _resolve(path).relative_to(_resolve(root))
        return True
    except ValueError:
        return False


def _is_same_or_child(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve(path: Path) -> Path:
    return path.resolve(strict=False)
