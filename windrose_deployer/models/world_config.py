"""Model for WorldDescription.json — per-world server settings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


COMBAT_DIFFICULTY_OPTIONS = [
    "WDS.Parameter.CombatDifficulty.Easy",
    "WDS.Parameter.CombatDifficulty.Normal",
    "WDS.Parameter.CombatDifficulty.Hard",
]

PRESET_OPTIONS = ["Easy", "Medium", "Hard", "Custom"]

FLOAT_PARAM_SPEC: dict[str, tuple[str, float, float, float]] = {
    # tag_key: (display_name, default, min, max)
    "WDS.Parameter.MobHealthMultiplier":              ("Mob Health Multiplier",              1.0, 0.2, 5.0),
    "WDS.Parameter.MobDamageMultiplier":              ("Mob Damage Multiplier",              1.0, 0.2, 5.0),
    "WDS.Parameter.ShipsHealthMultiplier":             ("Ship Health Multiplier",             1.0, 0.4, 5.0),
    "WDS.Parameter.ShipsDamageMultiplier":             ("Ship Damage Multiplier",             1.0, 0.2, 2.5),
    "WDS.Parameter.BoardingDifficultyMultiplier":      ("Boarding Difficulty Multiplier",     1.0, 0.2, 5.0),
    "WDS.Parameter.Coop.StatsCorrectionModifier":      ("Co-op Stats Correction Modifier",   1.0, 0.0, 2.0),
    "WDS.Parameter.Coop.ShipStatsCorrectionModifier":  ("Co-op Ship Stats Correction",       0.0, 0.0, 2.0),
}

BOOL_PARAM_SPEC: dict[str, tuple[str, bool]] = {
    # tag_key: (display_name, default)
    "WDS.Parameter.Coop.SharedQuests": ("Co-op Shared Quests", True),
    "WDS.Parameter.EasyExplore":       ("Immersive Exploration (hide POI markers)", False),
}


@dataclass
class WorldConfig:
    """Represents a single world's WorldDescription.json."""
    version: int = 1
    island_id: str = ""
    world_name: str = ""
    creation_time: float = 0.0
    world_preset_type: str = "Medium"

    bool_params: dict[str, bool] = field(default_factory=dict)
    float_params: dict[str, float] = field(default_factory=dict)
    combat_difficulty: str = "WDS.Parameter.CombatDifficulty.Normal"

    _raw: dict = field(default_factory=dict, repr=False)
    file_path: Optional[str] = None

    def to_json_dict(self) -> dict[str, Any]:
        out = dict(self._raw) if self._raw else {}
        out["Version"] = self.version

        wd: dict[str, Any] = out.get("WorldDescription", {})
        wd["islandId"] = self.island_id
        wd["WorldName"] = self.world_name
        wd["CreationTime"] = self.creation_time
        wd["WorldPresetType"] = self.world_preset_type

        ws: dict[str, Any] = {}

        bool_p: dict[str, bool] = {}
        for tag_key, value in self.bool_params.items():
            json_key = '{"TagName": "' + tag_key + '"}'
            bool_p[json_key] = value
        ws["BoolParameters"] = bool_p

        float_p: dict[str, Any] = {}
        for tag_key, value in self.float_params.items():
            json_key = '{"TagName": "' + tag_key + '"}'
            float_p[json_key] = value
        ws["FloatParameters"] = float_p

        tag_p: dict[str, Any] = {}
        cd_key = '{"TagName": "WDS.Parameter.CombatDifficulty"}'
        tag_p[cd_key] = {"TagName": self.combat_difficulty}
        ws["TagParameters"] = tag_p

        wd["WorldSettings"] = ws
        out["WorldDescription"] = wd
        return out

    @classmethod
    def from_json_dict(cls, d: dict[str, Any], file_path: Optional[str] = None) -> WorldConfig:
        wd = d.get("WorldDescription", {})
        ws = wd.get("WorldSettings", {})

        bool_params: dict[str, bool] = {}
        for raw_key, value in ws.get("BoolParameters", {}).items():
            tag = _extract_tag_name(raw_key)
            if tag:
                bool_params[tag] = bool(value)

        float_params: dict[str, float] = {}
        for raw_key, value in ws.get("FloatParameters", {}).items():
            tag = _extract_tag_name(raw_key)
            if tag:
                float_params[tag] = float(value)

        combat_diff = "WDS.Parameter.CombatDifficulty.Normal"
        for raw_key, value in ws.get("TagParameters", {}).items():
            tag = _extract_tag_name(raw_key)
            if tag == "WDS.Parameter.CombatDifficulty" and isinstance(value, dict):
                combat_diff = value.get("TagName", combat_diff)

        return cls(
            version=d.get("Version", 1),
            island_id=wd.get("islandId", wd.get("IslandId", "")),
            world_name=wd.get("WorldName", ""),
            creation_time=wd.get("CreationTime", 0.0),
            world_preset_type=wd.get("WorldPresetType", "Medium"),
            bool_params=bool_params,
            float_params=float_params,
            combat_difficulty=combat_diff,
            _raw=d,
            file_path=file_path,
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.world_name.strip():
            errors.append("World name must not be empty.")
        if self.world_preset_type not in PRESET_OPTIONS:
            errors.append(f"Invalid preset: {self.world_preset_type}")
        if self.combat_difficulty not in COMBAT_DIFFICULTY_OPTIONS:
            errors.append(f"Invalid combat difficulty: {self.combat_difficulty}")
        for tag_key, value in self.float_params.items():
            spec = FLOAT_PARAM_SPEC.get(tag_key)
            if spec:
                _, _, lo, hi = spec
                if not (lo <= value <= hi):
                    errors.append(f"{spec[0]}: {value} out of range [{lo}, {hi}]")
        return errors


def _extract_tag_name(raw_key: str) -> Optional[str]:
    """Extract the TagName value from a JSON-encoded key like '{"TagName": "X"}'."""
    import json
    try:
        parsed = json.loads(raw_key)
        if isinstance(parsed, dict):
            return parsed.get("TagName")
    except (json.JSONDecodeError, TypeError):
        pass
    return None
