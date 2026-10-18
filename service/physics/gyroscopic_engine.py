"""Asymmetric tyre-roll physics for the slipper-ball.

Model summary
-------------
* The ball is a thin disc rolling on its edge. ``lean`` is the signed tilt
  from vertical (radians): 0 = upright, +/- pi/2 = flat on its face. Positive
  lean tips the ball to the left of its heading (counter-clockwise turn).
* **Gyroscopic precession.** Gravity torques a leaning, spinning disc; the
  spin axis precesses at ``Omega_p = m g R sin(t) / (I * Omega)`` with spin
  ``Omega = v / R``. For a solid disc this is ``2 g sin(t) / v``: the slower
  the ball, the tighter it carves. That gives the natural *progressive* curve.
* **Peak Milk taper.** The beveled lid edge makes the two rims roll different
  radii, a fixed steering bias ``kappa = coupling * tan(alpha) / R`` that
  scales with speed (it fades as the ball slows, the opposite of precession).
* **Grass friction** decays speed (rolling resistance + drag, amplified by tilt).
* **Stability decay.** Stability ``s`` rises smoothly with speed. Below the
  stable speed the toppling rate dominates the self-righting rate, so tilt
  grows until it reaches the flat threshold (90 deg) = Flat Slap.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import NamedTuple

from service.core.config import PhysicsConfig
from service.core.types import Vec2, clamp, smoothstep

_HALF_PI = math.pi / 2.0


class StepStatus(Enum):
    ROLLING = auto()
    FLAT_SLAP = auto()


@dataclass(frozen=True, slots=True)
class StrikeImpulse:
    """What a stick strike does to the ball."""

    direction: Vec2
    speed: float
    tilt_recovery: float = 0.0  # radians of lean removed (bounded by tilt)
    lean_kick: float = 0.0  # signed radians added after recovery


class TrajectoryPoint(NamedTuple):
    t: float
    x: float
    y: float
    speed: float
    tilt: float


@dataclass(frozen=True, slots=True)
class PredictedTrajectory:
    points: tuple[TrajectoryPoint, ...]
    flat_after_s: float | None  # None if still upright at the horizon
    computed_at: float = 0.0

    @property
    def rest_point(self) -> Vec2:
        p = self.points[-1]
        return Vec2(p.x, p.y)


@dataclass(slots=True)
class TireBall:
    """Mutable ball state. Stored as scalars for speed in the hot loop."""

    x: float
    y: float
    hx: float  # unit heading vector
    hy: float
    speed: float
    lean: float  # signed tilt from vertical, radians
    z: float = 0.0
    age: float = 0.0
    distance: float = 0.0
    revision: int = 0  # bumps on launch/strike so forecasts can be invalidated
    is_flat: bool = False
    out_of_play: bool = False

    @property
    def position(self) -> Vec2:
        return Vec2(self.x, self.y)

    @property
    def heading(self) -> Vec2:
        return Vec2(self.hx, self.hy)

    @property
    def tilt(self) -> float:
        return abs(self.lean)

    @property
    def tilt_deg(self) -> float:
        return math.degrees(abs(self.lean))

    @property
    def is_live(self) -> bool:
        return not (self.is_flat or self.out_of_play)

    def copy(self) -> TireBall:
        return TireBall(self.x, self.y, self.hx, self.hy, self.speed,
                        self.lean, self.z, self.age, self.distance,
                        self.revision, self.is_flat, self.out_of_play)


class GyroscopicEngine:
    """Stateless-ish integrator (holds config and a seeded wobble RNG)."""

    def __init__(self, config: PhysicsConfig | None = None, seed: int = 0) -> None:
        self.cfg = config or PhysicsConfig()
        self._rng = random.Random(seed)
        c = self.cfg
        self._inertia = c.inertia_factor * c.mass_kg * c.radius_m ** 2
        self._tan_taper = math.tan(math.radians(c.taper_angle_deg))
        self._flat_rad = math.radians(c.flat_threshold_deg)

    # ------------------------------------------------------------ factories
    def launch(self, position: Vec2, heading: Vec2, speed: float,
               lean_rad: float, z: float = 0.0) -> TireBall:
        h = heading.normalized()
        if h.length_sq() == 0.0:
            raise ValueError("launch heading must be non-zero")
        if speed < 0.0:
            raise ValueError("launch speed must be >= 0")
        lim = self._flat_rad - 1e-3
        return TireBall(position.x, position.y, h.x, h.y, speed,
                        clamp(lean_rad, -lim, lim), z=z, revision=1)

    # --------------------------------------------------------- model terms
    def stability(self, speed: float) -> float:
        """0 (no gyroscopic stability) .. 1 (fully stable)."""
        c = self.cfg
        return smoothstep(c.v_collapse, c.v_stable, speed)

    def precession_rate(self, speed: float, lean: float) -> float:
        """Signed steering rate (rad/s) from gyroscopic precession."""
        c = self.cfg
        omega_spin = max(speed, c.speed_floor) / c.radius_m
        torque = c.mass_kg * c.gravity * c.radius_m * math.sin(abs(lean))
        rate = torque / (self._inertia * omega_spin)
        return rate if lean >= 0.0 else -rate

    def taper_rate(self, speed: float) -> float:
        """Signed steering rate (rad/s) from the asymmetric bevel."""
        c = self.cfg
        curvature = c.taper_coupling * self._tan_taper / c.radius_m
        return c.taper_handedness * curvature * speed

    def turn_rate(self, speed: float, lean: float) -> float:
        c = self.cfg
        total = self.precession_rate(speed, lean) + self.taper_rate(speed)
        return clamp(total, -c.max_turn_rate, c.max_turn_rate)

    def deceleration(self, speed: float, tilt: float) -> float:
        c = self.cfg
        rolling = c.rolling_resistance * c.gravity * (1.0 + c.tilt_scrub * math.sin(tilt))
        return rolling + c.air_drag * speed * speed

    # ------------------------------------------------------------ stepping
    def step(self, ball: TireBall, dt: float, noise: bool = True) -> StepStatus:
        """Advance ``ball`` in place by ``dt`` seconds."""
        if ball.is_flat:
            return StepStatus.FLAT_SLAP
        if ball.out_of_play:
            return StepStatus.ROLLING
        c = self.cfg
        v = ball.speed
        lean = ball.lean
        tilt = abs(lean)

        # 1) Steering: rotate the heading vector by the net turn rate.
        ang = self.turn_rate(v, lean) * dt
        if ang != 0.0:
            cs, sn = math.cos(ang), math.sin(ang)
            hx = ball.hx * cs - ball.hy * sn
            hy = ball.hx * sn + ball.hy * cs
            n = math.hypot(hx, hy)
            ball.hx, ball.hy = hx / n, hy / n

        # 2) Grass friction.
        v_new = max(0.0, v - self.deceleration(v, tilt) * dt)

        # 3) Translate along the (new) heading using mean speed.
        ds = 0.5 * (v + v_new) * dt
        ball.x += ball.hx * ds
        ball.y += ball.hy * ds
        ball.distance += ds
        ball.speed = v_new
        ball.age += dt

        # 4) Stability decay: toppling vs self-righting.
        s = self.stability(v_new)
        topple = c.fall_gain * (1.0 - s) ** 2 * (c.fall_seed_rad + math.sin(tilt))
        right = c.righting_gain * s * tilt
        rate = topple - right
        if noise and c.wobble_amp > 0.0:
            rate += c.wobble_amp * (1.0 - s) * self._rng.uniform(-1.0, 1.0)
        tilt = clamp(tilt + rate * dt, 0.0, _HALF_PI)

        sign = 1.0 if lean > 0.0 else -1.0 if lean < 0.0 else float(c.taper_handedness)
        if tilt >= self._flat_rad - 1e-12:
            ball.lean = sign * _HALF_PI
            ball.speed = 0.0
            ball.is_flat = True
            return StepStatus.FLAT_SLAP
        ball.lean = sign * tilt
        return StepStatus.ROLLING

    def apply_strike(self, ball: TireBall, impulse: StrikeImpulse) -> None:
        """Apply a stick impulse: new velocity, bounded re-stabilisation."""
        if not ball.is_live:
            raise ValueError("cannot strike a dead ball")
        d = impulse.direction.normalized()
        if d.length_sq() == 0.0:
            raise ValueError("strike direction must be non-zero")
        sign = 1.0 if ball.lean >= 0.0 else -1.0
        new_tilt = max(math.radians(1.0), ball.tilt - max(0.0, impulse.tilt_recovery))
        lim = self._flat_rad - 0.2
        ball.lean = clamp(sign * new_tilt + impulse.lean_kick, -lim, lim)
        ball.hx, ball.hy = d.x, d.y
        ball.speed = max(0.0, impulse.speed)
        ball.revision += 1

    # ---------------------------------------------------------- prediction
    def predict(self, ball: TireBall, horizon_s: float = 8.0, dt: float = 1 / 30,
                bounds: tuple[float, float, float, float] | None = None
                ) -> PredictedTrajectory:
        """Deterministic (noise-free) forward simulation on a copy."""
        sim = ball.copy()
        pts = [TrajectoryPoint(0.0, sim.x, sim.y, sim.speed, sim.tilt)]
        flat_after: float | None = 0.0 if sim.is_flat else None
        t = 0.0
        if flat_after is None:
            for _ in range(max(1, int(horizon_s / dt))):
                status = self.step(sim, dt, noise=False)
                t += dt
                pts.append(TrajectoryPoint(t, sim.x, sim.y, sim.speed, sim.tilt))
                if status is StepStatus.FLAT_SLAP:
                    flat_after = t
                    break
                if bounds is not None and not (
                    bounds[0] <= sim.x <= bounds[1] and bounds[2] <= sim.y <= bounds[3]
                ):
                    break
        return PredictedTrajectory(tuple(pts), flat_after)
