import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Controls, PlayStart, PlayStep, Replay, ReplayEvent } from "../types";
import { ApiRequestError } from "./api";
import { endPlay, startPlay, stepPlay } from "./play";
import { frameWidth } from "./replay";
import { usePlay } from "./usePlay";

vi.mock("./play", () => ({ startPlay: vi.fn(), stepPlay: vi.fn(), endPlay: vi.fn() }));

const PLAYERS = ["A1", "B1"];
const frame = () => new Array<number>(frameWidth(PLAYERS.length)).fill(0);
const controls: Controls = { move: [1, 0], aim: [1, 0], charge: false };
const getControls = () => controls;
const result: Replay["result"] = {
  score_a: 3, score_b: 1, winner: "A", reason: "time", sim_time_s: 120, live_time_s: 90,
};
const started = (session = "abc"): PlayStart => ({
  session, side: "B", schema: { head: [], player_fields: [], phases: {} }, players: PLAYERS, frame: frame(),
});
const events = (n: number, tag: string): ReplayEvent[] =>
  Array.from({ length: n }, (_, i) => ({ t: i, kind: "point", text: `${tag}${i}` }));
const step = (over: Partial<PlayStep> = {}): PlayStep => ({
  frame: frame(), events: [], finished: false, ticks: 1, ...over,
});
// A step that never answers until the match is aborted, like a slow server.
const hang = (_session: string, _controls: Controls, _players: number, signal?: AbortSignal) =>
  new Promise<PlayStep>((_resolve, reject) => {
    signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  });

beforeEach(() => {
  vi.mocked(startPlay).mockReset();
  vi.mocked(stepPlay).mockReset();
  vi.mocked(endPlay).mockReset();
});
afterEach(() => vi.restoreAllMocks());

describe("usePlay", () => {
  it("starts idle with nothing to draw", () => {
    const { result: hook } = renderHook(() => usePlay(getControls));
    expect(hook.current.status).toBe("idle");
    expect(hook.current.snapshot()).toBeNull();
  });

  it("plays to the end, keeps the result and tells the server", async () => {
    vi.mocked(startPlay).mockResolvedValue(started());
    vi.mocked(stepPlay)
      .mockResolvedValueOnce(step({ events: events(1, "e") }))
      .mockResolvedValueOnce(step({ finished: true, result }));
    const { result: hook } = renderHook(() => usePlay(getControls));
    await act(async () => {
      await hook.current.start({ minutes: 2 });
    });
    expect(hook.current.status).toBe("over");
    expect(hook.current.side).toBe("B");
    expect(hook.current.result).toEqual(result);
    expect(hook.current.events).toHaveLength(1);
    expect(stepPlay).toHaveBeenCalledWith("abc", controls, 2, expect.any(AbortSignal));
    expect(endPlay).toHaveBeenCalledWith("abc");
    const snap = hook.current.snapshot();
    expect(snap?.players.map((p) => p.id)).toEqual(PLAYERS);
  });

  it("keeps only the latest events and allows a missing result", async () => {
    vi.mocked(startPlay).mockResolvedValue(started());
    vi.mocked(stepPlay)
      .mockResolvedValueOnce(step({ events: events(30, "a") }))
      .mockResolvedValueOnce(step({ events: events(30, "b") }))
      .mockResolvedValueOnce(step({ finished: true }));
    const { result: hook } = renderHook(() => usePlay(getControls));
    await act(async () => {
      await hook.current.start({});
    });
    expect(hook.current.events).toHaveLength(40);
    expect(hook.current.events[39].text).toBe("b29");
    expect(hook.current.result).toBeNull();
  });

  it("shows the server's message when starting fails", async () => {
    vi.mocked(startPlay).mockRejectedValue(new ApiRequestError("too many matches", "busy", 503));
    const { result: hook } = renderHook(() => usePlay(getControls));
    await act(async () => {
      await hook.current.start({});
    });
    expect(hook.current.status).toBe("error");
    expect(hook.current.error).toBe("too many matches");
    expect(endPlay).not.toHaveBeenCalled();
  });

  it("falls back to a generic message for unknown errors", async () => {
    vi.mocked(startPlay).mockRejectedValue("boom");
    const { result: hook } = renderHook(() => usePlay(getControls));
    await act(async () => {
      await hook.current.start({});
    });
    expect(hook.current.error).toBe("Unexpected error");
  });

  it("reports a failed step and still ends the match", async () => {
    vi.mocked(startPlay).mockResolvedValue(started());
    vi.mocked(stepPlay).mockRejectedValue(new Error("lost connection"));
    const { result: hook } = renderHook(() => usePlay(getControls));
    await act(async () => {
      await hook.current.start({});
    });
    expect(hook.current.status).toBe("error");
    expect(hook.current.error).toBe("lost connection");
    expect(endPlay).toHaveBeenCalledWith("abc");
  });

  it("stops quietly when asked to, without showing an error", async () => {
    vi.mocked(startPlay).mockResolvedValue(started());
    vi.mocked(stepPlay).mockImplementation(hang);
    const { result: hook } = renderHook(() => usePlay(getControls));
    act(() => {
      void hook.current.start({});
    });
    await waitFor(() => expect(stepPlay).toHaveBeenCalled());
    expect(hook.current.status).toBe("playing");
    act(() => hook.current.stop());
    expect(hook.current.status).toBe("idle");
    await waitFor(() => expect(endPlay).toHaveBeenCalledWith("abc"));
    expect(hook.current.error).toBeNull();
  });

  it("ends the previous match when a new one starts", async () => {
    vi.mocked(startPlay).mockResolvedValueOnce(started("one")).mockResolvedValueOnce(started("two"));
    vi.mocked(stepPlay).mockImplementation(hang);
    const { result: hook } = renderHook(() => usePlay(getControls));
    act(() => {
      void hook.current.start({});
    });
    await waitFor(() => expect(stepPlay).toHaveBeenCalledTimes(1));
    act(() => {
      void hook.current.start({});
    });
    await waitFor(() => expect(endPlay).toHaveBeenCalledWith("one"));
    await waitFor(() => expect(stepPlay).toHaveBeenCalledTimes(2));
  });

  it("ends the match when the screen is closed", async () => {
    vi.mocked(startPlay).mockResolvedValue(started());
    vi.mocked(stepPlay).mockImplementation(hang);
    const { result: hook, unmount } = renderHook(() => usePlay(getControls));
    act(() => {
      void hook.current.start({});
    });
    await waitFor(() => expect(stepPlay).toHaveBeenCalled());
    unmount();
    await waitFor(() => expect(endPlay).toHaveBeenCalledWith("abc"));
  });
});
