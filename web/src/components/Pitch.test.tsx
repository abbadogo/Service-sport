import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Snapshot } from "../lib/replay";
import type { Roster } from "../types";
import { drawScene } from "../lib/draw";
import { Pitch } from "./Pitch";

vi.mock("../lib/draw", () => ({ PITCH_L: 100, PITCH_W: 50, drawScene: vi.fn() }));

let resize: (w: number) => void = () => {};
const disconnectSpy = vi.fn();
class FakeObserver {
  constructor(cb: (e: unknown[]) => void) {
    resize = (w) => cb([{ contentRect: { width: w } }]);
  }
  observe() {}
  disconnect = disconnectSpy;
}
const ctx = { setTransform: vi.fn() };
const getContext = vi.fn();
const snap = { phase: 1 } as unknown as Snapshot;

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", FakeObserver);
  getContext.mockReturnValue(ctx);
  HTMLCanvasElement.prototype.getContext = getContext as never;
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("Pitch", () => {
  it("renders an accessible canvas sized from the pitch ratio", () => {
    render(<Pitch snapshot={null} />);
    const c = screen.getByRole("img");
    expect(c.getAttribute("aria-label")).toContain("Top-down view");
    expect(c.style.height).toBe("400px");
  });

  it("draws the scene at the default width", () => {
    render(<Pitch snapshot={snap} />);
    expect(drawScene).toHaveBeenLastCalledWith(ctx, snap, 800, undefined);
    expect(ctx.setTransform).toHaveBeenCalled();
  });

  it("redraws and resizes when the container width changes", () => {
    render(<Pitch snapshot={snap} />);
    act(() => resize(500));
    expect(drawScene).toHaveBeenLastCalledWith(ctx, snap, 500, undefined);
    expect(screen.getByRole("img").style.height).toBe("250px");
  });

  it("never goes narrower than 280px", () => {
    render(<Pitch snapshot={snap} />);
    act(() => resize(100));
    expect(drawScene).toHaveBeenLastCalledWith(ctx, snap, 280, undefined);
  });

  it("stops observing on unmount", () => {
    const { unmount } = render(<Pitch snapshot={null} />);
    unmount();
    expect(disconnectSpy).toHaveBeenCalled();
  });

  it("skips drawing when the canvas has no 2d context", () => {
    getContext.mockReturnValue(null);
    render(<Pitch snapshot={snap} />);
    expect(drawScene).not.toHaveBeenCalled();
  });
});

describe("Pitch roster profiles", () => {
  it("passes the roster profiles to drawScene for the labels", () => {
    const profiles = { A1: { name: "Musa Danjuma", shirt: 7 } };
    const roster = { profiles, squads: {} } as unknown as Roster;
    render(<Pitch snapshot={snap} roster={roster} />);
    expect(drawScene).toHaveBeenLastCalledWith(ctx, snap, 800, profiles);
  });
});
