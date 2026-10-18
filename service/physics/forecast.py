"""Shared, cached ball forecasts so both teams' AI reuse one prediction."""

from __future__ import annotations

from dataclasses import replace

from service.physics.gyroscopic_engine import (
    GyroscopicEngine,
    PredictedTrajectory,
    TireBall,
)


class BallForecaster:
    """Recomputes at most every ``refresh_s`` or when the ball is struck."""

    def __init__(self, engine: GyroscopicEngine, horizon_s: float = 8.0,
                 sample_dt: float = 1 / 20, refresh_s: float = 0.1,
                 bounds: tuple[float, float, float, float] | None = None) -> None:
        self._engine = engine
        self._horizon = horizon_s
        self._dt = sample_dt
        self._refresh = refresh_s
        self._bounds = bounds
        self._cache: PredictedTrajectory | None = None
        self._rev = -1

    def invalidate(self) -> None:
        self._cache = None

    def get(self, ball: TireBall, now: float) -> PredictedTrajectory:
        c = self._cache
        if c is None or ball.revision != self._rev or now - c.computed_at >= self._refresh:
            traj = self._engine.predict(ball, self._horizon, self._dt, self._bounds)
            c = replace(traj, computed_at=now)
            self._cache, self._rev = c, ball.revision
        return c
