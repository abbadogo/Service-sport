import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePlay } from "./usePlay";

const h = vi.hoisted(() => ({ startPlay: vi.fn(), stepPlay: vi.fn(), endPlay: vi.fn() }));
vi.mock("./play", () => ({
  startPlay: h.startPlay,
  stepPlay: h.stepPlay,
  endPlay: h.endPlay,
}));

const BASE = { session: "s1", side: "A", schema: {}, players: ["a1"], frame: [] };
const PROFILES = { a1: { name: "Umar Jibrin", shirt: 1, team: "A" } };
const SQUADS = { A: { name: "Kano Stars", overall: 62, players: [] } };
const controls = () => ({ move: [0, 0] as [number, number], aim: [0, 0] as [number, number], charge: false });

beforeEach(() => {
  h.startPlay.mockReset();
  h.endPlay.mockReset();
  h.stepPlay.mockReset();
  h.stepPlay.mockResolvedValue({ frame: [], events: [], finished: true, ticks: 1, result: null });
});

async function play(response: object, result: { current: ReturnType<typeof usePlay> }) {
  h.startPlay.mockResolvedValueOnce(response);
  await act(async () => {
    await result.current.start({ side: "A" });
  });
}

describe("usePlay roster", () => {
  it("keeps the names and squads sent with the start response", async () => {
    const { result } = renderHook(() => usePlay(controls));
    await play({ ...BASE, profiles: PROFILES, squads: SQUADS }, result);
    expect(result.current.roster).toEqual({ profiles: PROFILES, squads: SQUADS });
  });

  it("has no roster for a match with random players", async () => {
    const { result } = renderHook(() => usePlay(controls));
    await play(BASE, result);
    expect(result.current.roster).toBeNull();
  });

  it("drops the old roster when the next match has none", async () => {
    const { result } = renderHook(() => usePlay(controls));
    await play({ ...BASE, profiles: PROFILES, squads: SQUADS }, result);
    expect(result.current.roster).not.toBeNull();
    await play(BASE, result);
    expect(result.current.roster).toBeNull();
  });
});
