"""Hold-to-charge strike power bar.

Human or AI "presses" to start the bar filling and "releases" to strike; the
level at the moment of release (0..1) sets how hard the strike is. For an AI
player ``target`` is the level it is willing to hold at; for a human controller
leave ``target`` at 1.0 so a long press means a full bar.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PowerBar:
    rate: float = 1.0       # level gained per second while held (1 / charge_time)
    level: float = 0.0
    target: float = 1.0
    charging: bool = False

    def press(self, target: float = 1.0) -> None:
        self.target = min(1.0, max(0.0, target))
        self.level = 0.0
        self.charging = True

    def update(self, dt: float) -> None:
        if self.charging:
            self.level = min(self.target, self.level + self.rate * dt)

    def cancel(self) -> None:
        self.level, self.charging = 0.0, False

    def release(self, min_level: float = 0.0) -> float:
        """Read the level, reset the bar, and return the strike level."""
        lv = max(self.level, min_level) if self.charging else min_level
        self.cancel()
        return min(1.0, max(0.0, lv))
