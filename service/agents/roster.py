"""Named players with FIFA-style ratings, and the squads they form.

A rating runs from 1 to 99 (50 is an average player). Ratings turn into the numbers the engine
already uses, so nothing about the rules changes:

- ``pace``      top running speed
- ``power``     strike power multiplier
- ``accuracy``  fewer mishits and a straighter aim
- ``endurance`` slower stamina drain while running
- ``reach``     how far the stick reaches

All names in the shipped squads (``squads/``) are made up.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from service.core.types import TEAM_SIZE, lerp

RATING_MIN: int = 1
RATING_MAX: int = 99
RATING_FIELDS: tuple[str, ...] = ("pace", "power", "accuracy", "endurance", "reach")
_PLAYER_KEYS = frozenset(("name", "shirt") + RATING_FIELDS)

# Engine values at rating 1 and rating 99. Rating 50 lands close to the old random average.
PACE_MPS = (6.0, 7.5)
POWER_MULT = (0.9, 1.1)
REACH_M = (1.1, 1.5)
DRAIN_MULT = (1.3, 0.7)     # high endurance drains stamina more slowly
MISHIT_MULT = (1.4, 0.6)    # high accuracy mishits less often
AIM_ERROR_MULT = (1.4, 0.6)  # ...and misses the aim by less


def _t(rating: int) -> float:
    """Rating 1..99 as a fraction 0..1."""
    return (rating - RATING_MIN) / (RATING_MAX - RATING_MIN)


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    """One named player and their ratings."""

    name: str
    shirt: int
    pace: int = 50
    power: int = 50
    accuracy: int = 50
    endurance: int = 50
    reach: int = 50

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("a player needs a name")
        if isinstance(self.shirt, bool) or not isinstance(self.shirt, int) or not 1 <= self.shirt <= 99:
            raise ValueError(f"{self.name}: shirt must be a whole number from 1 to 99")
        for field in RATING_FIELDS:
            v = getattr(self, field)
            if isinstance(v, bool) or not isinstance(v, int) or not RATING_MIN <= v <= RATING_MAX:
                raise ValueError(
                    f"{self.name}: {field} must be a whole number from {RATING_MIN} to {RATING_MAX}")

    @property
    def overall(self) -> int:
        """The single headline number, the average of the five ratings."""
        return round(sum(getattr(self, f) for f in RATING_FIELDS) / len(RATING_FIELDS))

    # Ratings turned into engine numbers.
    @property
    def max_speed(self) -> float:
        return lerp(PACE_MPS[0], PACE_MPS[1], _t(self.pace))

    @property
    def strength(self) -> float:
        return lerp(POWER_MULT[0], POWER_MULT[1], _t(self.power))

    @property
    def reach_m(self) -> float:
        return lerp(REACH_M[0], REACH_M[1], _t(self.reach))

    @property
    def drain_mult(self) -> float:
        return lerp(DRAIN_MULT[0], DRAIN_MULT[1], _t(self.endurance))

    @property
    def mishit_mult(self) -> float:
        return lerp(MISHIT_MULT[0], MISHIT_MULT[1], _t(self.accuracy))

    @property
    def aim_mult(self) -> float:
        return lerp(AIM_ERROR_MULT[0], AIM_ERROR_MULT[1], _t(self.accuracy))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PlayerProfile:
        if not isinstance(data, Mapping):
            raise ValueError("each player must be an object")
        unknown = set(data) - _PLAYER_KEYS
        if unknown:
            raise ValueError(f"unknown player field(s): {', '.join(sorted(unknown))}")
        for key in ("name", "shirt"):
            if key not in data:
                raise ValueError(f"a player needs a {key}")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class Squad:
    """A team's players, in slot order: slot 0 stands closest to the team's own baseline."""

    name: str
    players: tuple[PlayerProfile, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("a squad needs a name")
        if len(self.players) != TEAM_SIZE:
            raise ValueError(
                f"{self.name}: a squad needs exactly {TEAM_SIZE} players, got {len(self.players)}")
        shirts = [p.shirt for p in self.players]
        if len(set(shirts)) != len(shirts):
            raise ValueError(f"{self.name}: two players share a shirt number")

    @property
    def overall(self) -> int:
        return round(sum(p.overall for p in self.players) / len(self.players))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Squad:
        if not isinstance(data, Mapping):
            raise ValueError("a squad must be an object")
        unknown = set(data) - {"name", "players"}
        if unknown:
            raise ValueError(f"unknown squad field(s): {', '.join(sorted(unknown))}")
        if "name" not in data or "players" not in data:
            raise ValueError("a squad needs a name and a players list")
        players = data["players"]
        if not isinstance(players, list):
            raise ValueError("players must be a list")
        return cls(name=data["name"], players=tuple(PlayerProfile.from_dict(p) for p in players))


def load_squad(path: str | Path) -> Squad:
    """Read a squad from a JSON file (see the ``squads/`` folder for examples)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        raise ValueError(f"cannot read squad file {path}: {exc.strerror or exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    return Squad.from_dict(data)
