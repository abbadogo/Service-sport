import type { ReplayEvent } from "../types";

interface Props {
  events: ReplayEvent[];
  time: number;
  onJump: (t: number) => void;
}

export function EventLog({ events, time, onJump }: Props) {
  const shown = events.filter((e) => e.t <= time && e.kind !== "serve").reverse();
  return (
    <section className="card" aria-label="Match log">
      <h2>Match log</h2>
      {shown.length === 0 ? (
        <p className="muted">Nothing yet.</p>
      ) : (
        <ul className="log">
          {shown.map((e, i) => (
            <li key={`${e.t}-${i}`} className={e.kind}>
              <button type="button" onClick={() => onJump(Math.max(0, e.t - 4))}>
                <time>{e.t.toFixed(0)}s</time> {e.text}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
