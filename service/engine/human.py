"""Input from a human player (keyboard, touch or anything else that can produce these numbers)."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HumanInput:
    """One tick of controls for the player the human currently controls.

    ``move`` and ``aim`` are direction vectors with each component in [-1, 1]. ``charge`` is
    whether the strike button is held: holding fills the power bar, releasing swings.
    """

    move_x: float = 0.0
    move_y: float = 0.0
    aim_x: float = 0.0
    aim_y: float = 0.0
    charge: bool = False

    def __post_init__(self) -> None:
        for name in ("move_x", "move_y", "aim_x", "aim_y"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"{name} must be a finite number")
            if not -1.0 <= v <= 1.0:
                raise ValueError(f"{name} must be between -1 and 1")
        if not isinstance(self.charge, bool):
            raise ValueError("charge must be true or false")
