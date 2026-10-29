/* eslint-disable @typescript-eslint/no-explicit-any */
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlayView } from "./PlayView";

const h = vi.hoisted(() => ({
  play: {} as any,
  getControls: null as any,
  joystick: null as any,
  strike: null as any,
  eventLog: null as any,
}));

vi.mock("../lib/usePlay", () => ({
  usePlay: (gc: unknown) => {
    h.getControls = gc;
    return h.play;
  },
}));
vi.mock("./Joystick", () => ({
  Joystick: (p: any) => {
    h.joystick = p;
    return <div data-testid="joystick" />;
  },
}));
vi.mock("./StrikeButton", () => ({
  StrikeButton: (p: any) => {
    h.strike = p;
    return <div data-testid="strike" />;
  },
}));
vi.mock("./EventLog", () => ({
  EventLog: (p: any) => {
    h.eventLog = p;
    return <div data-testid="eventlog" />;
  },
}));
vi.mock("./Pitch", () => ({ Pitch: () => <div data-testid="pitch" /> }));
vi.mock("./Scoreboard", () => ({ Scoreboard: () => <div data-testid="score" /> }));

function setPlay(over: Record<string, unknown> = {}) {
  h.play = {
    status: "idle",
    error: null,
    events: [],
    side: "A",
    result: null,
    start: vi.fn(),
    stop: vi.fn(),
    snapshot: vi.fn(() => ({
      t: 1,
      players: [{ isCursor: true, team: "A", id: "P1", power: 0.5 }],
    })),
    ...over,
  };
}

describe("PlayView", () => {
  beforeEach(() => {
    vi.stubGlobal("requestAnimationFrame", vi.fn(() => 1));
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    setPlay();
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows an enabled Start button when idle", () => {
    render(<PlayView />);
    const btn = screen.getByRole("button", { name: "Start match" }) as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
    expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
    expect(screen.queryAllByRole("alert")).toHaveLength(0);
  });

  it("disables Start and shows an error for invalid minutes", () => {
    render(<PlayView />);
    fireEvent.change(screen.getByLabelText(/minutes/i), { target: { value: "99" } });
    const btn = screen.getByRole("button", { name: "Start match" }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(screen.queryAllByRole("alert").length).toBeGreaterThan(0);
  });

  it("starts a match as side A with the chosen minutes", () => {
    render(<PlayView />);
    fireEvent.change(screen.getByLabelText(/minutes/i), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Start match" }));
    expect(h.play.start).toHaveBeenCalledWith(
      expect.objectContaining({ side: "A", minutes: 3, seed: expect.any(Number) }),
    );
  });

  it("shows Starting... and disables the button while starting", () => {
    setPlay({ status: "starting" });
    render(<PlayView />);
    const btn = screen.getByRole("button", { name: "Starting..." }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("shows Stop while playing, polls snapshots, and names the player", () => {
    setPlay({ status: "playing" });
    render(<PlayView />);
    const raf = (globalThis as any).requestAnimationFrame as ReturnType<typeof vi.fn>;
    act(() => {
      raf.mock.calls[0][0](0);
    });
    expect(h.play.snapshot).toHaveBeenCalled();
    expect(screen.getByText(/You are P1/)).toBeTruthy();
    expect(h.strike.level).toBe(0.5);
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    expect(h.play.stop).toHaveBeenCalled();
  });

  it("cancels the animation frame when unmounted", () => {
    setPlay({ status: "playing" });
    const { unmount } = render(<PlayView />);
    unmount();
    expect((globalThis as any).cancelAnimationFrame).toHaveBeenCalled();
  });

  it("shows the full-time result and any error", () => {
    setPlay({
      status: "over",
      error: "Boom",
      result: { score_a: 3, score_b: 2, reason: "TIME_UP" },
    });
    render(<PlayView />);
    expect(screen.getByText(/Full time: 3 to 2, ended by time up\./)).toBeTruthy();
    expect(screen.getByText("Boom")).toBeTruthy();
  });

  it("builds controls from the keyboard while playing", () => {
    setPlay({ status: "playing" });
    render(<PlayView />);
    expect(h.getControls().charge).toBe(false);
    fireEvent.keyDown(window, { code: "Space" });
    expect(h.getControls().charge).toBe(true);
    fireEvent.keyUp(window, { code: "Space" });
    expect(h.getControls().charge).toBe(false);
    fireEvent.keyDown(window, { code: "ArrowRight" });
    expect(h.getControls().move).not.toEqual([0, 0]);
    fireEvent.blur(window);
    expect(h.getControls().move).toEqual([0, 0]);
  });

  it("ignores the keyboard when not playing", () => {
    render(<PlayView />);
    fireEvent.keyDown(window, { code: "Space" });
    expect(h.getControls().charge).toBe(false);
  });

  it("uses joystick and strike button input", () => {
    setPlay({ status: "playing" });
    render(<PlayView />);
    act(() => h.joystick.onChange([1, 0]));
    expect(h.getControls().move[0]).toBeGreaterThan(0);
    act(() => h.strike.onChange(true));
    expect(h.getControls().charge).toBe(true);
    act(() => h.strike.onChange(false));
    expect(h.getControls().charge).toBe(false);
    expect(() => h.eventLog.onJump()).not.toThrow();
  });
});
