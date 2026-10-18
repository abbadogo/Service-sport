"""Countdown clock: 15-minute cap, live-only ticking, sudden-death support."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

MAX_DURATION_MINUTES: float = 15.0
DEFAULT_DURATION_MINUTES: float = 15.0


class ClockState(Enum):
    READY = auto()    # created, never run
    RUNNING = auto()  # ball is live
    PAUSED = auto()   # dead ball / hand pickup
    EXPIRED = auto()  # regulation reached 00:00


class PauseReason(Enum):
    NOT_STARTED = auto()
    HAND_PICKUP = auto()
    OTHER = auto()


@dataclass(frozen=True, slots=True)
class DurationResolution:
    requested: float | None
    effective: float
    clamped: bool


def resolve_duration(minutes: float | None) -> DurationResolution:
    """Validate a requested duration.

    * ``None``  -> default (15 min)
    * > 15      -> clamped to exactly 15 (``clamped=True``)
    * <= 0, NaN, infinite, or non-numeric -> ``ValueError``
    """
    if minutes is None:
        return DurationResolution(None, DEFAULT_DURATION_MINUTES, False)
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)):
        raise ValueError(f"duration must be a number of minutes, got {minutes!r}")
    m = float(minutes)
    if not math.isfinite(m) or m <= 0.0:
        raise ValueError(f"duration must satisfy 0 < minutes <= {MAX_DURATION_MINUTES:g}, got {minutes!r}")
    if m > MAX_DURATION_MINUTES:
        return DurationResolution(m, MAX_DURATION_MINUTES, True)
    return DurationResolution(m, m, False)


class MatchClock:
    """Ticks down only while RUNNING. The state machine owns pause/resume."""

    def __init__(self, duration_minutes: float | None = None) -> None:
        self.resolution = resolve_duration(duration_minutes)
        self.total_s = self.resolution.effective * 60.0
        self._remaining = self.total_s
        self._state = ClockState.READY
        self._pause_reason: PauseReason | None = PauseReason.NOT_STARTED
        self._live_s = 0.0
        self._paused_s = 0.0
        self._overtime_s = 0.0
        self._in_overtime = False

    # --------------------------------------------------------------- views
    @property
    def state(self) -> ClockState:
        return self._state

    @property
    def pause_reason(self) -> PauseReason | None:
        return self._pause_reason

    @property
    def remaining_s(self) -> float:
        return self._remaining

    @property
    def live_elapsed_s(self) -> float:
        return self._live_s

    @property
    def paused_elapsed_s(self) -> float:
        return self._paused_s

    @property
    def overtime_s(self) -> float:
        return self._overtime_s

    @property
    def in_overtime(self) -> bool:
        return self._in_overtime

    @property
    def is_running(self) -> bool:
        return self._state is ClockState.RUNNING

    @property
    def expired(self) -> bool:
        return self._state is ClockState.EXPIRED or self._in_overtime

    @property
    def display(self) -> str:
        if self._in_overtime:
            s = int(self._overtime_s)
            return f"SD +{s // 60:02d}:{s % 60:02d}"
        s = int(math.ceil(self._remaining - 1e-9))
        return f"{s // 60:02d}:{s % 60:02d}"

    # ------------------------------------------------------------ commands
    def resume(self) -> None:
        """Ball goes live. No-op once regulation has expired (until overtime)."""
        if self._state in (ClockState.READY, ClockState.PAUSED):
            self._state = ClockState.RUNNING
            self._pause_reason = None

    def pause(self, reason: PauseReason = PauseReason.HAND_PICKUP) -> None:
        if self._state is ClockState.RUNNING:
            self._state = ClockState.PAUSED
            self._pause_reason = reason

    def tick(self, dt: float) -> bool:
        """Advance by ``dt`` sim-seconds. Returns True on the tick regulation
        time hits 00:00. Only RUNNING consumes time; PAUSED accumulates
        ``paused_elapsed_s`` for diagnostics."""
        if not math.isfinite(dt) or dt < 0.0:
            raise ValueError(f"dt must be finite and >= 0, got {dt!r}")
        if self._state is ClockState.RUNNING:
            if self._in_overtime:
                self._overtime_s += dt
                return False
            self._live_s += dt
            self._remaining -= dt
            if self._remaining <= 1e-9:
                self._remaining = 0.0
                self._state = ClockState.EXPIRED
                return True
        elif self._state in (ClockState.PAUSED, ClockState.READY):
            self._paused_s += dt
        return False

    def begin_overtime(self, ball_live: bool) -> None:
        """Enter sudden death after a tied expiry."""
        if self._state is not ClockState.EXPIRED:
            raise RuntimeError("overtime can only begin from EXPIRED")
        self._in_overtime = True
        if ball_live:
            self._state = ClockState.RUNNING
            self._pause_reason = None
        else:
            self._state = ClockState.PAUSED
            self._pause_reason = PauseReason.HAND_PICKUP
