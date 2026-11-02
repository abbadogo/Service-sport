/* eslint-disable @typescript-eslint/no-explicit-any */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlayView } from "./PlayView";

const h = vi.hoisted(() => ({ start: null as any, fetchSquads: null as any, roster: null as any }));

vi.mock("../lib/usePlay", () => ({
  usePlay: () => ({
    status: "idle",
    error: null,
    events: [],
    side: "A",
    result: null,
    start: h.start,
    stop: () => undefined,
    snapshot: () => null,
    roster: h.roster,
  }),
}));
vi.mock("../lib/api", () => ({
  fetchSquads: (...args: unknown[]) => h.fetchSquads(...args),
}));
vi.mock("./Joystick", () => ({ Joystick: () => null }));
vi.mock("./StrikeButton", () => ({ StrikeButton: () => null }));
vi.mock("./EventLog", () => ({ EventLog: () => null }));
vi.mock("./Pitch", () => ({ Pitch: () => null }));
vi.mock("./Scoreboard", () => ({ Scoreboard: () => null }));

const squad = (id: string, name: string) => ({ id, name, overall: 60, players: [] });
const SQUADS = [squad("kano_stars", "Kano Stars"), squad("gwale_maestros", "Gwale Maestros")];

beforeEach(() => {
  h.start = vi.fn();
  h.roster = null;
});
afterEach(cleanup);

describe("PlayView squad picker", () => {
  it("starts with random players unless a squad is picked", async () => {
    h.fetchSquads = vi.fn().mockResolvedValue(SQUADS);
    render(<PlayView />);
    await screen.findByLabelText("Your squad");
    fireEvent.click(screen.getByRole("button", { name: "Start match" }));
    expect(h.start).toHaveBeenCalledTimes(1);
    expect(h.start.mock.calls[0][0]).toEqual({ side: "A", minutes: 2, seed: expect.any(Number) });
  });

  it("sends the chosen squads for both sides", async () => {
    h.fetchSquads = vi.fn().mockResolvedValue(SQUADS);
    render(<PlayView />);
    const mine = await screen.findByLabelText("Your squad");
    fireEvent.change(mine, { target: { value: "kano_stars" } });
    fireEvent.change(screen.getByLabelText("Opponent squad"), { target: { value: "gwale_maestros" } });
    fireEvent.click(screen.getByRole("button", { name: "Start match" }));
    expect(h.start.mock.calls[0][0]).toMatchObject({
      side: "A",
      squad_a: "kano_stars",
      squad_b: "gwale_maestros",
    });
  });

  it("lists every squad with its overall rating", async () => {
    h.fetchSquads = vi.fn().mockResolvedValue(SQUADS);
    render(<PlayView />);
    await screen.findByLabelText("Your squad");
    expect(screen.getAllByRole("option", { name: "Kano Stars (60)" })).toHaveLength(2);
  });

  it("still starts a match when the squad list cannot be loaded", async () => {
    h.fetchSquads = vi.fn().mockRejectedValue(new Error("down"));
    render(<PlayView />);
    await waitFor(() => expect(h.fetchSquads).toHaveBeenCalled());
    expect(screen.queryByLabelText("Your squad")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Start match" }));
    expect(h.start.mock.calls[0][0]).toEqual({ side: "A", minutes: 2, seed: expect.any(Number) });
  });
});

describe("PlayView squad panel", () => {
  it("shows the squads of a match played with named players", async () => {
    h.fetchSquads = vi.fn().mockRejectedValue(new Error("down"));
    h.roster = { profiles: {}, squads: { A: { name: "Kano Stars", overall: 62, players: [] } } };
    render(<PlayView />);
    expect(await screen.findByRole("heading", { name: /Kano Stars \(62\)/ })).toBeTruthy();
  });

  it("shows no panel for random players", async () => {
    h.fetchSquads = vi.fn().mockRejectedValue(new Error("down"));
    render(<PlayView />);
    await waitFor(() => expect(h.fetchSquads).toHaveBeenCalled());
    expect(screen.queryByRole("region", { name: "Squads" })).toBeNull();
  });
});
