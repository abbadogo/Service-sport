import type { Roster, SquadPlayer } from "../types";

interface Props {
  roster: Roster | null | undefined;
  side: "A" | "B";
}

const SIDES = ["A", "B"] as const;

const COLUMNS: { key: keyof SquadPlayer; label: string; title: string }[] = [
  { key: "overall", label: "OVR", title: "Overall" },
  { key: "pace", label: "PAC", title: "Pace" },
  { key: "power", label: "POW", title: "Power" },
  { key: "accuracy", label: "ACC", title: "Accuracy" },
  { key: "endurance", label: "END", title: "Endurance" },
  { key: "reach", label: "RCH", title: "Reach" },
];

/** The two squads of a live match: shirt numbers, names and ratings. Hidden for random players. */
export function SquadPanel({ roster, side }: Props) {
  if (!roster) return null;
  return (
    <section className="card squads" aria-label="Squads">
      {SIDES.map((team) => {
        const squad = roster.squads[team];
        if (!squad) return null;
        return (
          <div key={team} className="squad">
            <h3>
              {squad.name} ({squad.overall}){team === side ? " · you" : ""}
            </h3>
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Player</th>
                    {COLUMNS.map((c) => (
                      <th key={c.key} scope="col" title={c.title}>
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {squad.players.map((p) => (
                    <tr key={p.shirt}>
                      <td>{p.shirt}</td>
                      <td>{p.name}</td>
                      {COLUMNS.map((c) => (
                        <td key={c.key}>{p[c.key]}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </section>
  );
}
