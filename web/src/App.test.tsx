/* eslint-disable @typescript-eslint/no-explicit-any */
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const h = vi.hoisted(() => ({
  fetchSettings: vi.fn(),
  runMatch: vi.fn(),
  pb: {} as any,
  panel: null as any,
  log: null as any,
}));

vi.mock("./lib/api", () => ({
  ApiRequestError: class ApiRequestError extends Error {},
  fetchSettings: (...a: unknown[]) => h.fetchSettings(...a),
  runMatch: (...a: unknown[]) => h.runMatch(...a),
}));
vi.mock("./lib/replay", () => ({
  replayDuration: () => 100,
  sampleAt: () => ({ t: 1 }),
}));
vi.mock("./lib/usePlayback", () => ({ usePlayback: () => h.pb }));
vi.mock("./lib/settings", () => ({
  changedSettings: vi.fn(() => ({ changed: true })),
  validateMinutes: () => null,
  validateSeed: () => null,
  validateSetting: () => null,
}));
vi.mock("./components/PlayView", () => ({ PlayView: () => <div>play-view</div> }));
vi.mock("./components/Pitch", () => ({ Pitch: () => <div /> }));
vi.mock("./components/Scoreboard", () => ({ Scoreboard: () => <div /> }));
vi.mock("./components/EventLog", () => ({
  EventLog: (p: any) => {
    h.log = p;
    return <div />;
  },
}));
vi.mock("./components/SettingsPanel", () => ({
  SettingsPanel: (p: any) => {
    h.panel = p;
    return <div>settings-panel</div>;
  },
}));

const specs = [{ key: "gravity", default: 9 }];
const replay = {
  events: [],
  result: { score_a: 3, score_b: 1, reason: "TIME_UP" },
  duration: { requested: 30, effective: 15, clamped: true },
};

function openWatch() {
  render(<App />);
  fireEvent.click(screen.getByRole("tab", { name: "Watch and tune" }));
}
const runBtn = () => screen.getByRole("button", { name: /run match|running match/i }) as HTMLButtonElement;

describe("App", () => {
  beforeEach(() => {
    h.fetchSettings.mockResolvedValue(specs);
    h.runMatch.mockResolvedValue(replay);
    h.pb = {
      playing: false,
      speed: 1,
      time: 50,
      toggle: vi.fn(),
      setSpeed: vi.fn(),
      seek: vi.fn(),
    };
  });
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("starts on the Play tab and switches to Watch and back", () => {
    render(<App />);
    expect(screen.getByText("play-view")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Watch and tune" }));
    expect(screen.queryByText("play-view")).toBeNull();
    expect(runBtn()).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Play" }));
    expect(screen.getByText("play-view")).toBeTruthy();
  });

  it("enables Run once settings load, then runs and shows the replay", async () => {
    openWatch();
    expect(runBtn().disabled).toBe(true);
    await waitFor(() => expect(runBtn().disabled).toBe(false));
    expect(screen.getByText("settings-panel")).toBeTruthy();

    fireEvent.change(document.getElementById("opening")!, { target: { value: "B" } });
    fireEvent.click(runBtn());
    expect(runBtn().textContent).toMatch(/Running match/);

    await screen.findByText(/Result: 3 to 1, ended by time up\./);
    expect(h.runMatch).toHaveBeenCalledWith(
      expect.objectContaining({ minutes: 2, seed: 1, opening_server: "B" }),
      expect.anything(),
    );
    expect(screen.getByText(/Requested 30 minutes; matches are capped at 15\./)).toBeTruthy();
  });

  it("shows an error when settings fail to load", async () => {
    h.fetchSettings.mockRejectedValue(new Error("boom"));
    openWatch();
    await screen.findByText("Could not load settings: boom");
  });

  it("shows an error when the match fails", async () => {
    h.runMatch.mockRejectedValue(new Error("bad match"));
    openWatch();
    await waitFor(() => expect(runBtn().disabled).toBe(false));
    fireEvent.click(runBtn());
    await screen.findByText("bad match");
  });

  it("falls back to a generic message for unknown errors", async () => {
    h.runMatch.mockRejectedValue("nope");
    openWatch();
    await waitFor(() => expect(runBtn().disabled).toBe(false));
    fireEvent.click(runBtn());
    await screen.findByText("Unexpected error");
  });

  it("ignores a settings failure that arrives after unmount", async () => {
    let reject!: (e: Error) => void;
    let signal!: AbortSignal;
    h.fetchSettings.mockImplementation(
      (s: AbortSignal) =>
        new Promise((_, rej) => {
          signal = s;
          reject = rej;
        }),
    );
    const { unmount } = render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: "Watch and tune" }));
    unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => {
      reject(new Error("late"));
    });
    expect(screen.queryByText(/late/)).toBeNull();
  });

  it("drives playback controls and settings panel callbacks", async () => {
    openWatch();
    await waitFor(() => expect(runBtn().disabled).toBe(false));
    fireEvent.click(runBtn());
    await screen.findByText(/Result: 3 to 1/);

    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    expect(h.pb.toggle).toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/speed/i), { target: { value: "4" } });
    expect(h.pb.setSpeed).toHaveBeenCalledWith(4);

    fireEvent.change(screen.getByLabelText("Replay position"), { target: { value: "250" } });
    expect(h.pb.seek).toHaveBeenCalledWith(25);

    act(() => h.panel.onChange("gravity", "12"));
    act(() => h.panel.onReset());
    act(() => h.log.onJump(10));
    expect(h.pb.seek).toHaveBeenCalledWith(10);
  });

  it("shows Pause while playing", () => {
    h.pb.playing = true;
    openWatch();
    expect(screen.getByRole("button", { name: "Pause" })).toBeTruthy();
  });
});
