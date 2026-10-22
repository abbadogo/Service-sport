import type { Vec } from "../types";

const KEY_DIRECTIONS: Record<string, Vec> = {
  KeyW: [0, -1], ArrowUp: [0, -1],
  KeyS: [0, 1], ArrowDown: [0, 1],
  KeyA: [-1, 0], ArrowLeft: [-1, 0],
  KeyD: [1, 0], ArrowRight: [1, 0],
};

export const isMoveKey = (code: string) => code in KEY_DIRECTIONS;

const length = (v: Vec) => Math.hypot(v[0], v[1]);

/** WASD / arrow keys to a movement vector (screen directions: up is -y). Diagonals have length 1. */
export function keysToVector(keys: ReadonlySet<string>): Vec {
  let x = 0;
  let y = 0;
  for (const code of keys) {
    const d = KEY_DIRECTIONS[code];
    if (d) {
      x += d[0];
      y += d[1];
    }
  }
  const len = Math.hypot(x, y);
  return len > 1 ? [x / len, y / len] : [x, y];
}

/** A touch-stick drag (pixels from the centre) to a vector inside the unit circle, with a small dead zone. */
export function stickVector(dx: number, dy: number, radius: number, deadZone = 0.15): Vec {
  if (radius <= 0) return [0, 0];
  const len = Math.hypot(dx, dy) / radius;
  if (len < deadZone) return [0, 0];
  const k = Math.min(1, len) / len;
  return [(dx / radius) * k, (dy / radius) * k];
}

/** Whichever of two inputs is pushed harder (so keyboard and touch can be used together). */
export const strongest = (a: Vec, b: Vec): Vec => (length(a) >= length(b) ? a : b);

/** The strike direction follows where you last moved; with no movement it keeps pointing the same way. */
export function updateAim(previous: Vec, move: Vec): Vec {
  const len = length(move);
  return len > 0.3 ? [move[0] / len, move[1] / len] : previous;
}
