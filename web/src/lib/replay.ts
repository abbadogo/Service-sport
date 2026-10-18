import type { Replay } from "../types";

// Frame layout: must match service/recording.py (FRAME_HEAD / PLAYER_FIELDS).
export const H = {
  T: 0, PHASE: 1, CLOCK: 2, SCORE_A: 3, SCORE_B: 4, CURSOR_A: 5, CURSOR_B: 6,
  BALL_X: 7, BALL_Y: 8, BALL_TILT: 9, BALL_FLAT: 10, BALL_HX: 11, BALL_HY: 12,
} as const;
export const HEAD_LEN = 13;
export const PLAYER_STRIDE = 4; // x, y, stamina, power
export const PHASE = { HAND_PICKUP: 2, LIVE: 3, FINISHED: 4 } as const;

export interface PlayerState {
  id: string;
  team: "A" | "B";
  x: number;
  y: number;
  stamina: number;
  power: number;
  isCursor: boolean;
}

export interface Snapshot {
  t: number;
  phase: number;
  clock: number;
  scoreA: number;
  scoreB: number;
  ball: { x: number; y: number; tilt: number; flat: boolean; hx: number; hy: number } | null;
  players: PlayerState[];
}

export function validateReplay(r: Replay): void {
  if (r.schema.head.length !== HEAD_LEN || r.schema.player_fields.length !== PLAYER_STRIDE) {
    throw new Error("replay layout does not match this app version");
  }
  if (r.frames.length === 0) throw new Error("replay has no frames");
  const width = HEAD_LEN + PLAYER_STRIDE * r.players.length;
  if (r.frames.some((f) => f.length !== width)) throw new Error("replay frame has the wrong size");
}

export function replayDuration(r: Replay): number {
  return r.frames[r.frames.length - 1][H.T];
}

/** Index of the last frame whose time is <= t (0 if t precedes the first frame). */
export function findFrameIndex(frames: number[][], t: number): number {
  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (frames[mid][H.T] <= t) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

const lerp = (a: number, b: number, k: number) => a + (b - a) * k;

export function sampleAt(r: Replay, time: number): Snapshot {
  const t = Math.min(Math.max(time, 0), replayDuration(r));
  const i = findFrameIndex(r.frames, t);
  const a = r.frames[i];
  const b = r.frames[Math.min(i + 1, r.frames.length - 1)];
  const span = b[H.T] - a[H.T];
  const k = span > 0 ? (t - a[H.T]) / span : 0;
  const half = r.players.length / 2;
  const cursors = [a[H.CURSOR_A], a[H.CURSOR_B]];

  const players = r.players.map((id, n) => {
    const o = HEAD_LEN + n * PLAYER_STRIDE;
    return {
      id,
      team: n < half ? ("A" as const) : ("B" as const),
      x: lerp(a[o], b[o], k),
      y: lerp(a[o + 1], b[o + 1], k),
      stamina: a[o + 2],
      power: a[o + 3],
      isCursor: cursors.includes(n),
    };
  });

  const hasBall = a[H.BALL_X] >= 0;
  const bothBall = hasBall && b[H.BALL_X] >= 0;
  const ball = hasBall
    ? {
        x: bothBall ? lerp(a[H.BALL_X], b[H.BALL_X], k) : a[H.BALL_X],
        y: bothBall ? lerp(a[H.BALL_Y], b[H.BALL_Y], k) : a[H.BALL_Y],
        tilt: a[H.BALL_TILT],
        flat: a[H.BALL_FLAT] === 1,
        hx: a[H.BALL_HX],
        hy: a[H.BALL_HY],
      }
    : null;

  return { t, phase: a[H.PHASE], clock: a[H.CLOCK], scoreA: a[H.SCORE_A], scoreB: a[H.SCORE_B], ball, players };
}

/** Same display rules as the Python clock: countdown, or "SD +mm:ss" in sudden death (negative values). */
export function formatClock(value: number): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  if (value < 0) {
    const s = Math.floor(-value);
    return `SD +${pad(Math.floor(s / 60))}:${pad(s % 60)}`;
  }
  const s = Math.ceil(value - 1e-9);
  return `${pad(Math.floor(s / 60))}:${pad(s % 60)}`;
}
