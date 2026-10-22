import { describe, expect, it } from "vitest";
import { isMoveKey, keysToVector, stickVector, strongest, updateAim } from "./input";

describe("keysToVector", () => {
  it("maps WASD and arrow keys to screen directions", () => {
    expect(keysToVector(new Set(["KeyD"]))).toEqual([1, 0]);
    expect(keysToVector(new Set(["ArrowLeft"]))).toEqual([-1, 0]);
    expect(keysToVector(new Set(["KeyW"]))).toEqual([0, -1]);
    expect(keysToVector(new Set(["ArrowDown"]))).toEqual([0, 1]);
  });
  it("cancels opposite keys and ignores other keys", () => {
    expect(keysToVector(new Set(["KeyA", "KeyD"]))).toEqual([0, 0]);
    expect(keysToVector(new Set(["KeyQ", "Space"]))).toEqual([0, 0]);
    expect(keysToVector(new Set())).toEqual([0, 0]);
  });
  it("keeps diagonals at length 1", () => {
    const [x, y] = keysToVector(new Set(["KeyW", "KeyD"]));
    expect(Math.hypot(x, y)).toBeCloseTo(1);
    expect(x).toBeGreaterThan(0);
    expect(y).toBeLessThan(0);
  });
  it("recognises movement keys", () => {
    expect(isMoveKey("KeyW")).toBe(true);
    expect(isMoveKey("Space")).toBe(false);
  });
});

describe("stickVector", () => {
  it("has a dead zone near the centre", () => expect(stickVector(3, 3, 70)).toEqual([0, 0]));
  it("scales with the drag and stops at the edge of the circle", () => {
    expect(stickVector(35, 0, 70)).toEqual([0.5, 0]);
    const [x, y] = stickVector(500, 500, 70);
    expect(Math.hypot(x, y)).toBeCloseTo(1);
  });
  it("handles a zero radius", () => expect(stickVector(10, 10, 0)).toEqual([0, 0]));
});

describe("strongest / updateAim", () => {
  it("picks the harder push", () => expect(strongest([0.2, 0], [0, -0.9])).toEqual([0, -0.9]));
  it("aims where you last moved, and keeps the aim when you stop", () => {
    const moved = updateAim([1, 0], [0, -2]);
    expect(moved).toEqual([0, -1]);
    expect(updateAim(moved, [0, 0])).toEqual([0, -1]);
    expect(updateAim([1, 0], [0.1, 0.1])).toEqual([1, 0]); // too small to count
  });
});
