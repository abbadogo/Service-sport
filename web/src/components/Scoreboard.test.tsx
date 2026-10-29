import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PHASE, formatClock, type Snapshot } from "../lib/replay";
import { Scoreboard } from "./Scoreboard";

afterEach(cleanup);

const snap = (phase: Snapshot["phase"]) =>
  ({ phase, scoreA: 3, scoreB: 1, clock: 65 }) as unknown as Snapshot;

const text = (c: HTMLElement, sel: string) =>
  c.querySelector(sel)?.textContent;

describe("Scoreboard", () => {
  it("shows defaults with no snapshot", () => {
    const { container } = render(<Scoreboard snapshot={null} />);
    expect(text(container, ".score")).toBe("0 : 0");
    expect(text(container, ".clock")).toBe("--:--");
    expect(text(container, ".phase")).toBe("No match yet");
  });

  it.each([
    [PHASE.LIVE, "Ball live: clock running"],
    [PHASE.HAND_PICKUP, "Hand pickup: clock paused"],
    [PHASE.FINISHED, "Match finished"],
  ])("shows the right label for phase %s", (phase, label) => {
    const { container } = render(<Scoreboard snapshot={snap(phase)} />);
    expect(text(container, ".phase")).toBe(label);
    expect(text(container, ".score")).toBe("3 : 1");
    expect(text(container, ".clock")).toBe(formatClock(65 as never));
  });
});
