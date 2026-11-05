import { PHASE, formatClock, type Snapshot } from "../lib/replay";
import type { Roster } from "../types";

export function Scoreboard({
  snapshot,
  roster,
}: {
  snapshot: Snapshot | null;
  roster?: Roster | null;
}) {
  const phase =
    snapshot?.phase === PHASE.LIVE
      ? "Ball live: clock running"
      : snapshot?.phase === PHASE.HAND_PICKUP
        ? "Hand pickup: clock paused"
        : snapshot?.phase === PHASE.FINISHED
          ? "Match finished"
          : "No match yet";
  return (
    <section className="board" aria-label="Scoreboard">
      <div className="team a">{roster?.squads.A?.name ?? "Team A"}</div>
      <div className="mid">
        <div className="score">
          {snapshot?.scoreA ?? 0} : {snapshot?.scoreB ?? 0}
        </div>
        <div className="clock">{snapshot ? formatClock(snapshot.clock) : "--:--"}</div>
      </div>
      <div className="team b">{roster?.squads.B?.name ?? "Team B"}</div>
      <p className="phase" aria-live="polite">{phase}</p>
    </section>
  );
}
