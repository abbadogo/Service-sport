import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { Roster, SquadPlayer } from "../types";
import { SquadPanel } from "./SquadPanel";

const player = (name: string, shirt: number, n: number): SquadPlayer => ({
  name,
  shirt,
  overall: n,
  pace: n + 1,
  power: n + 2,
  accuracy: n + 3,
  endurance: n + 4,
  reach: n + 5,
});

const ROSTER: Roster = {
  profiles: {},
  squads: {
    A: { name: "Kano Stars", overall: 62, players: [player("Umar Jibrin", 7, 40), player("Aminu Kwana", 11, 50)] },
    B: { name: "Dala Warriors", overall: 58, players: [player("Sani Dala", 3, 70)] },
  },
};

afterEach(cleanup);

describe("SquadPanel", () => {
  it("shows nothing for a match with random players", () => {
    const { container } = render(<SquadPanel roster={null} side="A" />);
    expect(container.firstChild).toBeNull();
    const again = render(<SquadPanel roster={undefined} side="A" />);
    expect(again.container.firstChild).toBeNull();
  });

  it("lists both squads with their overall rating", () => {
    render(<SquadPanel roster={ROSTER} side="A" />);
    expect(screen.getByRole("heading", { name: /Kano Stars \(62\)/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Dala Warriors \(58\)/ })).toBeTruthy();
  });

  it("shows each player's shirt, name and ratings", () => {
    render(<SquadPanel roster={ROSTER} side="A" />);
    const row = screen.getByText("Umar Jibrin").closest("tr") as HTMLElement;
    for (const value of ["7", "40", "41", "42", "43", "44", "45"]) {
      expect(within(row).getByText(value)).toBeTruthy();
    }
    expect(screen.getByText("Sani Dala")).toBeTruthy();
  });

  it("marks the side you control", () => {
    render(<SquadPanel roster={ROSTER} side="B" />);
    expect(screen.getByRole("heading", { name: /Dala Warriors.*you/ })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: /Kano Stars.*you/ })).toBeNull();
  });

  it("skips a side that has no squad", () => {
    render(<SquadPanel roster={{ profiles: {}, squads: { A: ROSTER.squads.A } }} side="A" />);
    expect(screen.getAllByRole("table")).toHaveLength(1);
  });
});
