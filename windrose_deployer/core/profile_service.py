from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models.metadata import ModMetadata
from ..models.mod_install import ModInstall
from ..models.profile import Profile, ProfileEntry


@dataclass
class ProfileComparison:
    matching: list[ProfileEntry] = field(default_factory=list)
    to_install: list[ProfileEntry] = field(default_factory=list)
    to_uninstall: list[ModInstall] = field(default_factory=list)
    missing_archives: list[ProfileEntry] = field(default_factory=list)


def _entry_key(
    source_archive: str,
    targets: list[str],
    selected_variant: str = "",
    component_entries: list[str] | None = None,
) -> tuple:
    return (
        Path(source_archive).name.lower(),
        tuple(sorted(targets)),
        selected_variant or "",
        tuple(sorted(component_entries or [])),
    )


class ProfileService:
    def capture_current_state(
        self,
        *,
        name: str,
        mods: list[ModInstall],
        notes: str = "",
        server_settings_snapshot: dict | None = None,
        world_settings_snapshot: dict | None = None,
    ) -> Profile:
        profile = Profile.new(name=name, notes=notes)
        profile.entries = [
            ProfileEntry(
                display_name=mod.display_name,
                source_archive=mod.source_archive,
                targets=list(mod.targets),
                selected_variant=mod.selected_variant or "",
                mod_id=mod.mod_id,
                enabled=mod.enabled,
                component_entries=sorted(mod.component_map.keys()),
                metadata=ModMetadata.from_dict(mod.metadata.to_dict()),
            )
            for mod in sorted(mods, key=lambda item: (item.display_name.lower(), item.install_time))
        ]
        profile.server_settings_snapshot = dict(server_settings_snapshot or {})
        profile.world_settings_snapshot = dict(world_settings_snapshot or {})
        return profile

    def compare(self, profile: Profile, mods: list[ModInstall]) -> ProfileComparison:
        comparison = ProfileComparison()
        current_by_key = {
            _entry_key(mod.source_archive, mod.targets, mod.selected_variant or "", sorted(mod.component_map.keys())): mod
            for mod in mods
        }
        desired_keys = set()
        for entry in profile.entries:
            key = _entry_key(
                entry.source_archive,
                entry.targets,
                entry.selected_variant,
                entry.component_entries,
            )
            desired_keys.add(key)
            if key in current_by_key:
                comparison.matching.append(entry)
            else:
                if entry.source_archive and not Path(entry.source_archive).is_file():
                    comparison.missing_archives.append(entry)
                else:
                    comparison.to_install.append(entry)

        for mod in mods:
            key = _entry_key(mod.source_archive, mod.targets, mod.selected_variant or "", sorted(mod.component_map.keys()))
            if key not in desired_keys:
                comparison.to_uninstall.append(mod)

        return comparison
