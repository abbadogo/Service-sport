"""Immutable, validated configuration objects."""

from __future__ import annotations

import math
from dataclasses import dataclass

from service.core.types import Team


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PhysicsConfig:
    """Tunable constants for the slipper-ball (SI units)."""

    gravity: float = 9.81
    radius_m: float = 0.075
    mass_kg: float = 0.06
    inertia_factor: float = 0.5  # I_spin = factor * m * R^2 (0.5 = solid disc)

    # Peak Milk can-lid bevel: half-angle of the asymmetric edge taper.
    taper_angle_deg: float = 6.0
    # Fraction of the ideal cone-roll curvature that survives on a thin edge.
    taper_coupling: float = 0.0015
    # +1 curves left (CCW), -1 curves right. Fixed by which way the bevel faces.
    taper_handedness: int = 1

    # Grass friction.
    # Dimensionless Crr for an even, flat pitch (identical on both halves).
    rolling_resistance: float = 0.035
    air_drag: float = 0.009  # deceleration = air_drag * v^2
    tilt_scrub: float = 1.5  # extra friction as the tyre leans onto its face

    # Rotational stability model.
    v_stable: float = 3.0  # at/above: gyroscopic stability is full
    v_collapse: float = 0.6  # at/below: no gyroscopic stability at all
    fall_gain: float = 3.0  # toppling rate scale (1/s)
    fall_seed_rad: float = 0.1  # keeps a perfectly upright ball from sticking
    righting_gain: float = 2.0  # self-righting rate scale (1/s)
    wobble_amp: float = 0.25  # rad/s of seeded tilt noise at zero stability

    max_turn_rate: float = 3.0  # rad/s steering cap
    speed_floor: float = 0.5  # m/s floor in the precession denominator
    flat_threshold_deg: float = 90.0

    def __post_init__(self) -> None:
        for name in (
            "gravity", "radius_m", "mass_kg", "inertia_factor", "v_stable",
            "fall_gain", "max_turn_rate", "speed_floor", "flat_threshold_deg",
        ):
            _require(getattr(self, name) > 0.0, f"{name} must be > 0")
        for name in ("rolling_resistance", "air_drag", "tilt_scrub",
                     "righting_gain", "wobble_amp", "fall_seed_rad",
                     "taper_coupling"):
            _require(getattr(self, name) >= 0.0, f"{name} must be >= 0")
        _require(0.0 <= self.v_collapse < self.v_stable,
                 "need 0 <= v_collapse < v_stable")
        _require(0.0 <= self.taper_angle_deg < 45.0,
                 "taper_angle_deg must be in [0, 45)")
        _require(self.taper_handedness in (-1, 1), "taper_handedness is +/-1")
        _require(self.flat_threshold_deg <= 90.0,
                 "flat_threshold_deg must be <= 90")


@dataclass(frozen=True, slots=True)
class StaminaConfig:
    """Fatigue model shared by every player."""

    sprint_drain_per_s: float = 0.05  # at intensity 1.0
    rest_recovery_per_s: float = 0.04
    recovery_intensity: float = 0.35  # at/below this effort, stamina recovers
    fresh_threshold: float = 0.45  # at/above: full speed
    min_speed_fraction: float = 0.40  # speed multiplier at zero stamina
    exhausted_threshold: float = 0.15
    strike_cost: float = 0.015

    def __post_init__(self) -> None:
        _require(0.0 < self.fresh_threshold <= 1.0, "fresh_threshold in (0,1]")
        _require(0.0 < self.min_speed_fraction <= 1.0,
                 "min_speed_fraction in (0,1]")
        _require(0.0 <= self.exhausted_threshold <= 1.0,
                 "exhausted_threshold in [0,1]")


@dataclass(frozen=True, slots=True)
class StrikeConfig:
    """Hold-to-charge power bar. Level 0..1 is set by how long the bar was
    held before release; the strike speed is read off that level."""

    charge_time_s: float = 1.0      # empty -> full when held
    windup_range_m: float = 12.0    # the bar starts filling when the ball is this close
    min_level: float = 0.25         # level used if the stick connects with no wind-up
    min_speed: float = 5.5          # m/s at level 0
    max_speed: float = 15.0         # m/s at level 1 (full bar)
    aim_error_min_rad: float = 0.02  # accuracy cost: harder strikes are wilder
    aim_error_max_rad: float = 0.12
    # Chance a swing is a mishit (draft rule): worse when tired or when the ball is fast.
    mishit_base: float = 0.06
    mishit_per_mps_over_6: float = 0.015
    mishit_fatigue: float = 0.40
    mishit_max: float = 0.6
    mishit_min_speed: float = 2.5   # a mishit dribbles the ball off weakly...
    mishit_max_speed: float = 4.5
    mishit_aim_error_rad: float = 0.5  # ...and in the wrong direction
    # Long hit (draft rule): a (nearly) full bar sends the disc deep, aimed to die short of the far baseline.
    long_hit_level: float = 0.9
    long_hit_depth_m: float = 10.0       # aim to die this far short of the opponent's baseline
    long_hit_stamina_cost: float = 0.06  # on top of the normal strike cost
    long_hit_aim_error_rad: float = 0.04  # extra aim error on a long hit

    def __post_init__(self) -> None:
        _require(self.charge_time_s > 0.0, "charge_time_s must be > 0")
        _require(self.windup_range_m > 0.0, "windup_range_m must be > 0")
        _require(0.0 <= self.min_level <= 1.0, "min_level in [0,1]")
        _require(0.0 < self.min_speed <= self.max_speed, "need 0 < min_speed <= max_speed")
        _require(0.0 < self.long_hit_level <= 1.0, "long_hit_level in (0,1]")
        _require(self.long_hit_depth_m >= 0.0 and self.long_hit_stamina_cost >= 0.0,
                 "long hit values must be >= 0")

    def speed_for(self, level: float) -> float:
        lv = 0.0 if level < 0.0 else 1.0 if level > 1.0 else level
        return self.min_speed + (self.max_speed - self.min_speed) * lv

    def mishit_probability(self, ball_speed: float, speed_factor: float) -> float:
        """Probability that a swing mishits the ball."""
        p = (self.mishit_base + self.mishit_per_mps_over_6 * max(0.0, ball_speed - 6.0)
             + self.mishit_fatigue * (1.0 - speed_factor))
        return min(self.mishit_max, max(0.0, p))

    def aim_error_for(self, level: float) -> float:
        lv = 0.0 if level < 0.0 else 1.0 if level > 1.0 else level
        return self.aim_error_min_rad + (self.aim_error_max_rad - self.aim_error_min_rad) * lv


@dataclass(frozen=True, slots=True)
class MatchConfig:
    """Top-level match settings."""

    duration_minutes: float | None = None  # validated by MatchClock (<= 15)
    seed: int = 1
    tick_hz: int = 120
    opening_server: Team = Team.A
    max_serve_faults: int = 2
    out_of_bounds_concedes: bool = True
    require_crossing_between_team_strikes: bool = True
    rotate_after_point: bool = True  # the conceding team rotates positions one slot (draft rule)
    pickup_timeout_s: float = 90.0
    max_sim_seconds: float = 7200.0  # safety valve against runaway sims

    def __post_init__(self) -> None:
        _require(self.tick_hz >= 20, "tick_hz must be >= 20")
        _require(self.max_serve_faults >= 1, "max_serve_faults must be >= 1")
        _require(self.pickup_timeout_s > 0.0, "pickup_timeout_s must be > 0")
        _require(math.isfinite(self.max_sim_seconds) and self.max_sim_seconds > 0,
                 "max_sim_seconds must be finite and > 0")

    @property
    def dt(self) -> float:
        return 1.0 / self.tick_hz
