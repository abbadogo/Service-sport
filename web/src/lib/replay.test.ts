import { describe, expect, it } from "vitest";
import type { Replay } from "../types";
import { findFrameIndex, formatClock, replayDuration, sampleAt, validateReplay } from "./replay";

/** Two players (one a side), three frames at t = 0, 1, 2. */
function fixture(): Replay {
  const head = ["t", "phase", "clock", "score_a", "score_b", "cursor_a", "cursor_b", "ball_x", "ball_y", "ball_tilt", "ball_flat", "ball_hx", "ball_hy"];
  const row = (t: number, px: number, ballX: number, flat = 0) =>
    [t, 3, 100 - t, 1, 2, 0, -1, ballX, 30, 5, flat, 1, 0, px, 10, 0.8, 0.25, 90, 20, 0.5, 0];
  return {
    schema: { head, player_fields: ["x", "y", "stamina", "power"], phases: { LIVE: 3 } },
    players: ["A1", "B1"],
    frames: [row(0, 10, 20), row(1, 20, 30), row(2, 30, -1)],
    events: [],
    result: { score_a: 1, score_b: 2, winner: "B", reason: "CLOCK_EXPIRED", sim_time_s: 2, live_time_s: 2 },
    duration: { requested: 1, effective: 1, clamped: false },
  };
}

describe("findFrameIndex", () => {
  const frames = fixture().frames;
  it("finds the last frame at or before t", () => {
    expect(findFrameIndex(frames, 0)).toBe(0);
    expect(findFrameIndex(frames, 0.99)).toBe(0);
    expect(findFrameIndex(frames, 1)).toBe(1);
    expect(findFrameIndex(frames, 99)).toBe(2);
  });
  it("returns 0 before the first frame", () => expect(findFrameIndex(frames, -5)).toBe(0));
});

describe("sampleAt", () => {
  it("interpolates positions between frames", () => {
    const s = sampleAt(fixture(), 0.5);
    expect(s.players[0].x).toBeCloseTo(15);
    expect(s.ball?.x).toBeCloseTo(25);
  });
  it("assigns teams, cursors and scores", () => {
    const s = sampleAt(fixture(), 0);
    expect(s.players.map((p) => p.team)).toEqual(["A", "B"]);
    expect(s.players.map((p) => p.isCursor)).toEqual([true, false]);
    expect([s.scoreA, s.scoreB]).toEqual([1, 2]);
  });
  it("clamps time to the replay and handles a missing ball", () => {
    expect(sampleAt(fixture(), 999).t).toBe(2);
    expect(sampleAt(fixture(), 999).ball).toBeNull();
    expect(sampleAt(fixture(), -3).t).toBe(0);
  });
  it("reports duration", () => expect(replayDuration(fixture())).toBe(2));
});

describe("validateReplay", () => {
  it("accepts a well-formed replay", () => expect(() => validateReplay(fixture())).not.toThrow());
  it("rejects wrong frame sizes, empty frames and layout changes", () => {
    const bad = fixture();
    bad.frames[1] = bad.frames[1].slice(0, 5);
    expect(() => validateReplay(bad)).toThrow(/wrong size/);
    expect(() => validateReplay({ ...fixture(), frames: [] })).toThrow(/no frames/);
    const layout = fixture();
    layout.schema.head = ["t"];
    expect(() => validateReplay(layout)).toThrow(/layout/);
  });
});

describe("formatClock", () => {
  it("counts down and rounds up", () => {
    expect(formatClock(120)).toBe("02:00");
    expect(formatClock(59.2)).toBe("01:00");
    expect(formatClock(0)).toBe("00:00");
  });
  it("shows sudden death as elapsed time", () => expect(formatClock(-65.9)).toBe("SD +01:05"));
});
