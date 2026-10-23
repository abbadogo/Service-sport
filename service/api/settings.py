"""Editable engine settings: one table drives validation, defaults and the web panel.

To expose a new tunable, add a SettingSpec here; the API and the web UI pick it up.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from service.core.config import MatchConfig, PhysicsConfig, StaminaConfig, StrikeConfig


class SettingsError(ValueError):
    """An override was unknown, mistyped or out of range."""


@dataclass(frozen=True)
class SettingSpec:
    key: str
    group: str
    label: str
    description: str
    target: str  # "physics" | "strike" | "stamina" | "match"
    field: str
    minimum: float
    maximum: float
    step: float


SPECS: tuple[SettingSpec, ...] = (
    SettingSpec("bevel_strength", "Ball", "Bevel strength",
                "How hard the beveled edge pulls the ball sideways.",
                "physics", "taper_coupling", 0.0, 0.02, 0.0005),
    SettingSpec("bevel_angle_deg", "Ball", "Bevel angle (deg)",
                "Half-angle of the Peak Milk lid bevel.",
                "physics", "taper_angle_deg", 0.0, 20.0, 0.5),
    SettingSpec("grass_friction", "Pitch", "Grass friction",
                "Rolling resistance of the pitch (lower rolls farther).",
                "physics", "rolling_resistance", 0.01, 0.15, 0.005),
    SettingSpec("air_drag", "Pitch", "Air drag", "Speed-squared drag on the rolling ball.",
                "physics", "air_drag", 0.0, 0.03, 0.001),
    SettingSpec("mishit_base", "Strikes", "Base mishit chance",
                "Chance a fresh player mishits a slow ball.",
                "strike", "mishit_base", 0.0, 0.4, 0.01),
    SettingSpec("mishit_per_speed", "Strikes", "Mishit per m/s over 6",
                "Extra mishit chance for each m/s of ball speed over 6.",
                "strike", "mishit_per_mps_over_6", 0.0, 0.05, 0.005),
    SettingSpec("mishit_fatigue", "Strikes", "Mishit from fatigue",
                "Extra mishit chance as stamina runs out.",
                "strike", "mishit_fatigue", 0.0, 1.0, 0.05),
    SettingSpec("charge_time", "Strikes", "Bar charge time (s)", "Seconds to fill the strike power bar.",
                "strike", "charge_time_s", 0.3, 3.0, 0.1),
    SettingSpec("max_strike_speed", "Strikes", "Full-bar strike speed (m/s)",
                "Ball speed from a full power bar.",
                "strike", "max_speed", 8.0, 20.0, 0.5),
    SettingSpec("long_hit_level", "Strikes", "Long hit starts at bar level",
                "A bar at or above this level is a long hit: the disc is sent deep, short of the baseline.",
                "strike", "long_hit_level", 0.5, 1.0, 0.05),
    SettingSpec("long_hit_depth", "Strikes", "Long hit: stops this far short of the baseline (m)",
                "How far before the opponent's baseline a long hit is aimed to die.",
                "strike", "long_hit_depth_m", 0.0, 40.0, 1.0),
    SettingSpec("long_hit_cost", "Strikes", "Long hit stamina cost",
                "Extra stamina a long hit costs the striker.",
                "strike", "long_hit_stamina_cost", 0.0, 0.3, 0.01),
    SettingSpec("rotation", "Rules", "Rotate positions after each point",
                "1 = the team that conceded rotates one position slot (volleyball style); 0 = off.",
                "match", "rotate_after_point", 0.0, 1.0, 1.0),
    SettingSpec("human_swing_grace", "Playing yourself", "Swing forgiveness (s)",
                "Your swing reaches farther the faster the disc moves (speed x this). More = easier to hit.",
                "strike", "human_swing_grace_s", 0.0, 0.6, 0.05),
    SettingSpec("human_aim_assist", "Playing yourself", "Aim assist",
                "0 = the bevel bends your hits sideways; 1 = corrected so a straight hit stays straight.",
                "strike", "human_aim_assist", 0.0, 1.0, 0.1),
    SettingSpec("sprint_drain", "Players", "Sprint stamina drain /s",
                "Stamina lost per second at full sprint.",
                "stamina", "sprint_drain_per_s", 0.01, 0.3, 0.01),
    SettingSpec("rest_recovery", "Players", "Rest recovery /s", "Stamina regained per second at rest.",
                "stamina", "rest_recovery_per_s", 0.0, 0.2, 0.01),
)
_BY_KEY = {s.key: s for s in SPECS}
_DEFAULT_OBJECTS = {"physics": PhysicsConfig(), "strike": StrikeConfig(), "stamina": StaminaConfig(),
                    "match": MatchConfig()}


def default_for(spec: SettingSpec) -> float:
    return float(getattr(_DEFAULT_OBJECTS[spec.target], spec.field))


def public_specs() -> list[dict[str, Any]]:
    return [{"key": s.key, "group": s.group, "label": s.label, "description": s.description,
             "minimum": s.minimum, "maximum": s.maximum, "step": s.step, "default": default_for(s)}
            for s in SPECS]


def validate_overrides(overrides: Mapping[str, object]) -> dict[str, float]:
    clean: dict[str, float] = {}
    for key, value in overrides.items():
        spec = _BY_KEY.get(key)
        if spec is None:
            raise SettingsError(f"unknown setting: {key!r}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingsError(f"{key} must be a number")
        v = float(value)
        if not math.isfinite(v) or not spec.minimum <= v <= spec.maximum:
            raise SettingsError(f"{key} must be between {spec.minimum:g} and {spec.maximum:g}")
        clean[key] = v
    return clean


def build_configs(overrides: Mapping[str, object]) -> tuple[PhysicsConfig, StrikeConfig, StaminaConfig]:
    """Apply validated overrides on top of the defaults. Cross-field problems
    (for example max strike speed below the minimum) also raise SettingsError."""
    # Any: each group is unpacked into a different dataclass whose fields have different types.
    values: dict[str, dict[str, Any]] = {"physics": {}, "strike": {}, "stamina": {}, "match": {}}
    for key, v in validate_overrides(overrides).items():
        spec = _BY_KEY[key]
        values[spec.target][spec.field] = v
    try:
        return (PhysicsConfig(**values["physics"]), StrikeConfig(**values["strike"]),
                StaminaConfig(**values["stamina"]))
    except ValueError as exc:
        raise SettingsError(str(exc)) from exc


def match_fields(overrides: Mapping[str, object]) -> dict[str, Any]:
    """Match-level overrides (rules rather than physics), ready for MatchConfig(**fields)."""
    out: dict[str, Any] = {}
    for key, v in validate_overrides(overrides).items():
        spec = _BY_KEY[key]
        if spec.target == "match":
            out[spec.field] = v >= 0.5  # toggles are stored as 0 / 1
    return out
