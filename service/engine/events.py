"""Lifecycle enums and immutable event records emitted by the match."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from service.core.types import Team, Vec2


class MatchPhase(Enum):
    PREMATCH = auto()
    HAND_PICKUP = auto()  # dead ball, clock paused
    LIVE = auto()         # tyre rolling, clock running
    FINISHED = auto()


class MatchMode(Enum):
    REGULATION = auto()
    SUDDEN_DEATH = auto()


class PointReason(Enum):
    FLAT_SLAP = auto()
    OUT_OF_BOUNDS = auto()
    SERVE_FAULTS = auto()
    LAZY_SERVE = auto()  # serve died without crossing the midline: point against the server


class MatchEndReason(Enum):
    CLOCK_EXPIRED = auto()
    SUDDEN_DEATH_POINT = auto()
    ABORTED = auto()


@dataclass(frozen=True, slots=True)
class MatchEvent:
    sim_time: float
    clock: str


@dataclass(frozen=True, slots=True)
class PhaseChanged(MatchEvent):
    old: MatchPhase
    new: MatchPhase


@dataclass(frozen=True, slots=True)
class ServeLaunched(MatchEvent):
    team: Team
    server_id: str
    speed: float
    lean_deg: float


@dataclass(frozen=True, slots=True)
class ServeFault(MatchEvent):
    team: Team
    server_id: str
    faults: tuple[str, ...]
    fault_count: int


@dataclass(frozen=True, slots=True)
class StrikeMade(MatchEvent):
    team: Team
    player_id: str
    speed: float
    tilt_before_deg: float
    tilt_after_deg: float
    power: float
    long_hit: bool = False


@dataclass(frozen=True, slots=True)
class SwingMissed(MatchEvent):
    team: Team
    player_id: str


@dataclass(frozen=True, slots=True)
class TeamRotated(MatchEvent):
    team: Team


@dataclass(frozen=True, slots=True)
class StrikeMishit(MatchEvent):
    team: Team
    player_id: str
    speed: float


@dataclass(frozen=True, slots=True)
class CursorChanged(MatchEvent):
    team: Team
    player_id: str | None


@dataclass(frozen=True, slots=True)
class PointScored(MatchEvent):
    scorer: Team
    conceded_by: Team
    reason: PointReason
    position: Vec2
    score_a: int
    score_b: int
    chaser_id: str | None = None          # cursor who failed to reach it
    chaser_stamina: float | None = None   # their stamina at the time


@dataclass(frozen=True, slots=True)
class ZoneCorrection(MatchEvent):
    player_id: str


@dataclass(frozen=True, slots=True)
class SuddenDeathStarted(MatchEvent):
    score_a: int
    score_b: int


@dataclass(frozen=True, slots=True)
class MatchEnded(MatchEvent):
    winner: Team | None
    reason: MatchEndReason
    score_a: int
    score_b: int
