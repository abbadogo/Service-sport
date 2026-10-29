import { describe, expect, it } from "vitest";
import { PITCH_L, PITCH_W, drawScene } from "./draw";
import type { Snapshot } from "./replay";

function fakeCtx() {
  const fills: string[] = [];
  const strokes: string[] = [];
  const calls: Record<string, unknown[][]> = {};
  const store: Record<string, unknown> = {};
  const ctx = new Proxy(store, {
    get(t, k: string) {
      if (k in t) return t[k];
      return (...a: unknown[]) => {
        (calls[k] ??= []).push(a);
      };
    },
    set(t, k: string, v) {
      t[k] = v;
      if (k === "fillStyle") fills.push(String(v));
      if (k === "strokeStyle") strokes.push(String(v));
      return true;
    },
  }) as unknown as CanvasRenderingContext2D;
  return { ctx, calls, fills, strokes };
}

const player = (o: Record<string, unknown> = {}) => ({
  id: "A1", team: "A", x: 10, y: 20, isCursor: false, stamina: 0.9, power: 0, ...o,
});
const ball = (o: Record<string, unknown> = {}) => ({
  x: 30, y: 40, tilt: 0, hx: 1, hy: 0, flat: false, ...o,
});
const snap = (players: unknown[] = [], b: unknown = null) =>
  ({ players, ball: b }) as unknown as Snapshot;

describe("drawScene", () => {
  it("exports the pitch size", () => {
    expect([PITCH_L, PITCH_W]).toEqual([105, 68]);
  });

  it("draws only the pitch when there is no snapshot", () => {
    const { ctx, calls, fills } = fakeCtx();
    drawScene(ctx, null, 210);
    expect(calls.clearRect[0]).toEqual([0, 0, 210, 136]);
    expect(calls.fillRect).toHaveLength(17);
    expect(fills).toContain("#3a7d3d");
    expect(fills).toContain("#337636");
    expect(calls.arc).toBeUndefined();
    expect(calls.fillText).toBeUndefined();
  });

  it("colours players by team and labels them at scaled positions", () => {
    const { ctx, calls, fills } = fakeCtx();
    drawScene(ctx, snap([player(), player({ id: "B1", team: "B" })]), 210);
    expect(fills).toContain("#1f5fbf");
    expect(fills).toContain("#d6336c");
    expect(calls.fillText[0]).toEqual(["A1", 20, 40]);
    expect(calls.fillText[1]).toEqual(["B1", 20, 40]);
  });

  it.each([
    [0.1, "#ff5a4d"],
    [0.3, "#ffc23d"],
    [0.9, "#8be28b"],
  ])("stamina %s uses bar colour %s", (stamina, colour) => {
    const { ctx, fills } = fakeCtx();
    drawScene(ctx, snap([player({ stamina })]), 210);
    expect(fills).toContain(colour);
  });

  it("draws no power bar at rest", () => {
    const { ctx, calls } = fakeCtx();
    drawScene(ctx, snap([player({ power: 0 })]), 210);
    expect(calls.fillRect).toHaveLength(19);
  });

  it.each([
    [0.3, "#ffe066"],
    [0.6, "#ffb02e"],
    [0.9, "#ff4d4d"],
  ])("power %s draws a bar in %s", (power, colour) => {
    const { ctx, calls, fills } = fakeCtx();
    drawScene(ctx, snap([player({ power })]), 210);
    expect(calls.fillRect).toHaveLength(21);
    expect(fills).toContain(colour);
  });

  it("rings only the cursor player", () => {
    const a = fakeCtx();
    drawScene(a.ctx, snap([player()]), 210);
    expect(a.calls.arc).toHaveLength(1);
    expect(a.strokes).not.toContain("#ffe066");
    const b = fakeCtx();
    drawScene(b.ctx, snap([player({ isCursor: true })]), 210);
    expect(b.calls.arc).toHaveLength(2);
    expect(b.strokes).toContain("#ffe066");
  });

  it("draws an upright ball as a thin ellipse", () => {
    const { ctx, calls, fills } = fakeCtx();
    drawScene(ctx, snap([], ball()), 210);
    expect(calls.translate[0]).toEqual([60, 80]);
    expect(calls.rotate[0]).toEqual([0]);
    expect(calls.save).toHaveLength(1);
    expect(calls.restore).toHaveLength(1);
    expect(calls.ellipse[0][3] as number).toBeCloseTo(0.35);
    expect(fills).toContain("#ffd43b");
    expect(calls.arc).toBeUndefined();
  });

  it("widens the ball ellipse as it tilts", () => {
    const { ctx, calls } = fakeCtx();
    drawScene(ctx, snap([], ball({ tilt: 90 })), 210);
    expect(calls.ellipse[0][3] as number).toBeCloseTo(1.7);
  });

  it("draws a flat ball in orange with an outline ring", () => {
    const { ctx, calls, fills } = fakeCtx();
    drawScene(ctx, snap([], ball({ flat: true })), 210);
    expect(fills).toContain("#ff9f1c");
    expect(calls.arc).toHaveLength(1);
    expect(calls.arc[0].slice(0, 2)).toEqual([60, 80]);
    expect(calls.arc[0][2] as number).toBeCloseTo(3.2);
  });
});
