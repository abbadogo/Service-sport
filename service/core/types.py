"""Foundational value types, pitch constants and math helpers.

Coordinate system (metres): X runs along the pitch length (0 = Team A
baseline, 105 = Team B baseline), Y runs across the width (0..68), and Z is
height above the grass. Angles are radians, counter-clockwise positive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

PITCH_LENGTH_M: float = 105.0
PITCH_WIDTH_M: float = 68.0
MIDLINE_X_M: float = PITCH_LENGTH_M / 2.0
TEAM_SIZE: int = 6
EPS: float = 1e-9


class Team(Enum):
    """The two sides. Team A owns the left half, Team B the right half."""

    A = "A"
    B = "B"

    @property
    def opponent(self) -> Team:
        return Team.B if self is Team.A else Team.A

    @property
    def forward_sign(self) -> float:
        """+1 when 'forward' (toward the opponent) is +X, else -1."""
        return 1.0 if self is Team.A else -1.0

    @property
    def baseline_x(self) -> float:
        return 0.0 if self is Team.A else PITCH_LENGTH_M


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Hermite interpolation: 0 at/below edge0, 1 at/above edge1."""
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@dataclass(frozen=True, slots=True)
class Vec2:
    """Immutable 2D vector."""

    x: float = 0.0
    y: float = 0.0

    def __add__(self, o: Vec2) -> Vec2:
        return Vec2(self.x + o.x, self.y + o.y)

    def __sub__(self, o: Vec2) -> Vec2:
        return Vec2(self.x - o.x, self.y - o.y)

    def __mul__(self, k: float) -> Vec2:
        return Vec2(self.x * k, self.y * k)

    __rmul__ = __mul__

    def __truediv__(self, k: float) -> Vec2:
        return Vec2(self.x / k, self.y / k)

    def __neg__(self) -> Vec2:
        return Vec2(-self.x, -self.y)

    def dot(self, o: Vec2) -> float:
        return self.x * o.x + self.y * o.y

    def cross(self, o: Vec2) -> float:
        """Z component of the 3D cross product (positive = o is CCW of self)."""
        return self.x * o.y - self.y * o.x

    def length_sq(self) -> float:
        return self.x * self.x + self.y * self.y

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def distance_to(self, o: Vec2) -> float:
        return math.hypot(self.x - o.x, self.y - o.y)

    def normalized(self) -> Vec2:
        n = self.length()
        return Vec2(0.0, 0.0) if n < EPS else Vec2(self.x / n, self.y / n)

    def rotated(self, angle: float) -> Vec2:
        c, s = math.cos(angle), math.sin(angle)
        return Vec2(self.x * c - self.y * s, self.x * s + self.y * c)

    def perp_left(self) -> Vec2:
        return Vec2(-self.y, self.x)

    def angle(self) -> float:
        return math.atan2(self.y, self.x)

    def lerp(self, o: Vec2, t: float) -> Vec2:
        return Vec2(self.x + (o.x - self.x) * t, self.y + (o.y - self.y) * t)

    @staticmethod
    def from_angle(angle: float, length: float = 1.0) -> Vec2:
        return Vec2(math.cos(angle) * length, math.sin(angle) * length)
