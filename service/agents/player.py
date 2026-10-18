"""Player agent: position, speed, stamina and the movement primitive."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from service.agents.formation import home_position
from service.agents.power_bar import PowerBar
from service.core.config import StaminaConfig
from service.core.types import TEAM_SIZE, Team, Vec2, clamp, lerp


@dataclass(slots=True)
class Player:
    pid: str
    team: Team
    slot: int
    pos: Vec2
    max_speed: float          # m/s at full stamina and intensity 1.0
    reach: float              # stick + arm reach, metres
    strength: float           # strike power multiplier
    stamina: float = 1.0      # 1.0 fresh .. 0.0 spent
    strike_cooldown: float = 0.0
    crouched: bool = False
    distance_run: float = 0.0
    strikes: int = 0
    power_bar: PowerBar = field(default_factory=PowerBar, repr=False)
    cfg: StaminaConfig = field(default_factory=StaminaConfig, repr=False)

    # ------------------------------------------------------------- fatigue
    @property
    def speed_factor(self) -> float:
        c = self.cfg
        return lerp(c.min_speed_fraction, 1.0, clamp(self.stamina / c.fresh_threshold, 0.0, 1.0))

    @property
    def current_max_speed(self) -> float:
        return self.max_speed * self.speed_factor

    @property
    def is_exhausted(self) -> bool:
        return self.stamina < self.cfg.exhausted_threshold

    def spend_stamina(self, amount: float) -> None:
        self.stamina = clamp(self.stamina - amount, 0.0, 1.0)

    # ------------------------------------------------------------ movement
    def move_toward(self, target: Vec2, dt: float, intensity: float = 1.0) -> float:
        """Move toward ``target`` at ``intensity`` (0..1) of current top speed.
        Returns metres moved. Callers must pass zone-legal targets; the referee
        still re-checks every tick."""
        intensity = clamp(intensity, 0.0, 1.0)
        dx, dy = target.x - self.pos.x, target.y - self.pos.y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 1e-9 or intensity <= 0.0:
            self.rest(dt)
            return 0.0
        step = self.current_max_speed * intensity * dt
        if dist <= step:
            self.pos, moved = target, dist
        else:
            k = step / dist
            self.pos, moved = Vec2(self.pos.x + dx * k, self.pos.y + dy * k), step
        self.distance_run += moved
        c = self.cfg
        effort = intensity * (moved / step)
        self.stamina = clamp(self.stamina - c.sprint_drain_per_s * effort * effort * dt, 0.0, 1.0)
        if effort <= c.recovery_intensity:
            self.stamina = clamp(self.stamina + c.rest_recovery_per_s * dt, 0.0, 1.0)
        return moved

    def rest(self, dt: float) -> None:
        self.stamina = clamp(self.stamina + self.cfg.rest_recovery_per_s * dt, 0.0, 1.0)

    def tick_timers(self, dt: float) -> None:
        if self.strike_cooldown > 0.0:
            self.strike_cooldown = max(0.0, self.strike_cooldown - dt)


def build_team(team: Team, rng: random.Random, cfg: StaminaConfig | None = None) -> list[Player]:
    """Create a full squad standing in their home formation."""
    cfg = cfg or StaminaConfig()
    return [
        Player(
            pid=f"{team.value}{slot + 1}", team=team, slot=slot,
            pos=home_position(team, slot),
            max_speed=rng.uniform(6.0, 7.5), reach=1.3,
            strength=rng.uniform(0.9, 1.1), cfg=cfg,
        )
        for slot in range(TEAM_SIZE)
    ]
