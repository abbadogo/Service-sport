"""Foosball-style formation: columns, lateral lanes that slide with the ball.

Team B's layout is the 180-degree rotation of Team A's (point symmetry), so both
ends of the pitch are exactly alike, including the direction the bevel curves.
"""

from __future__ import annotations

from service.core.types import (
    MIDLINE_X_M,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    TEAM_SIZE,
    Team,
    Vec2,
    clamp,
)

COLUMN_FRACTIONS: tuple[float, ...] = (0.12, 0.26, 0.40, 0.54, 0.68, 0.82)  # from own baseline
LANE_SPACING_M: float = 8.0
LANE_TRACKING: float = 0.6  # how strongly the line follows the ball's Y
assert len(COLUMN_FRACTIONS) == TEAM_SIZE


def column_x(team: Team, slot: int) -> float:
    d = COLUMN_FRACTIONS[slot] * MIDLINE_X_M
    return d if team is Team.A else PITCH_LENGTH_M - d


def _lane_a(slot: int, ref_y: float) -> float:
    mid = PITCH_WIDTH_M / 2
    center = mid + (ref_y - mid) * LANE_TRACKING
    return clamp(center + (slot - (TEAM_SIZE - 1) / 2) * LANE_SPACING_M, 2.0, PITCH_WIDTH_M - 2.0)


def _lane(team: Team, slot: int, ref_y: float) -> float:
    if team is Team.A:
        return _lane_a(slot, ref_y)
    return PITCH_WIDTH_M - _lane_a(slot, PITCH_WIDTH_M - ref_y)  # rotate 180 degrees


def home_position(team: Team, slot: int) -> Vec2:
    return Vec2(column_x(team, slot), _lane(team, slot, PITCH_WIDTH_M / 2))


def guard_position(team: Team, slot: int, ref_y: float) -> Vec2:
    """Hold the column, slide laterally toward the ball's Y."""
    return Vec2(column_x(team, slot), _lane(team, slot, ref_y))
