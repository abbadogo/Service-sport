import { useEffect, useMemo, useRef, useState } from "react";
import { EventLog } from "./components/EventLog";
import { Pitch } from "./components/Pitch";
import { Scoreboard } from "./components/Scoreboard";
import { SettingsPanel } from "./components/SettingsPanel";
import { ApiRequestError, fetchSettings, runMatch } from "./lib/api";
import { replayDuration, sampleAt } from "./lib/replay";
import { changedSettings, validateMinutes, validateSeed, validateSetting } from "./lib/settings";
import { usePlayback } from "./lib/usePlayback";
import type { Replay, SettingSpec } from "./types";

type Match =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; replay: Replay };

const messageOf = (err: unknown) => (err instanceof ApiRequestError || err instanceof Error ? err.message : "Unexpected error");

export default function App() {
  const [specs, setSpecs] = useState<SettingSpec[]>([]);
  const [specsError, setSpecsError] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [minutes, setMinutes] = useState("2");
  const [seed, setSeed] = useState("1");
  const [opening, setOpening] = useState<"A" | "B">("A");
  const [match, setMatch] = useState<Match>({ status: "idle" });
  const inFlight = useRef<AbortController | null>(null);

  const resetValues = (list: SettingSpec[]) => setValues(Object.fromEntries(list.map((s) => [s.key, String(s.default)])));

  useEffect(() => {
    const c = new AbortController();
    fetchSettings(c.signal)
      .then((list) => {
        setSpecs(list);
        resetValues(list);
      })
      .catch((err) => {
        if (!c.signal.aborted) setSpecsError(messageOf(err));
      });
    return () => c.abort();
  }, []);

  const minutesError = validateMinutes(minutes);
  const seedError = validateSeed(seed);
  const settingsInvalid = specs.some((s) => validateSetting(s, values[s.key] ?? String(s.default)) !== null);
  const canRun = specs.length > 0 && !minutesError && !seedError && !settingsInvalid && match.status !== "loading";

  async function run() {
    inFlight.current?.abort();
    const c = new AbortController();
    inFlight.current = c;
    setMatch({ status: "loading" });
    try {
      const replay = await runMatch(
        { minutes: Number(minutes), seed: Number(seed), opening_server: opening, settings: changedSettings(specs, values) },
        c.signal,
      );
      if (!c.signal.aborted) setMatch({ status: "ready", replay });
    } catch (err) {
      if (!c.signal.aborted) setMatch({ status: "error", message: messageOf(err) });
    }
  }

  const replay = match.status === "ready" ? match.replay : null;
  const duration = replay ? replayDuration(replay) : 0;
  const pb = usePlayback(duration);
  const snapshot = useMemo(() => (replay ? sampleAt(replay, pb.time) : null), [replay, pb.time]);

  return (
    <main>
      <header>
        <h1>Sabis Lab</h1>
        <p className="muted">Run a match, watch it, change the rules, run it again.</p>
      </header>

      <div className="layout">
        <div>
          <section className="card controls" aria-label="Match options">
            <div className="field">
              <label htmlFor="minutes">Minutes (max 15)</label>
              <input id="minutes" value={minutes} onChange={(e) => setMinutes(e.target.value)} inputMode="decimal" aria-invalid={minutesError !== null} />
              {minutesError && <small role="alert" className="error">{minutesError}</small>}
            </div>
            <div className="field">
              <label htmlFor="seed">Seed</label>
              <input id="seed" value={seed} onChange={(e) => setSeed(e.target.value)} inputMode="numeric" aria-invalid={seedError !== null} />
              {seedError && <small role="alert" className="error">{seedError}</small>}
            </div>
            <div className="field">
              <label htmlFor="opening">Opening server</label>
              <select id="opening" value={opening} onChange={(e) => setOpening(e.target.value as "A" | "B")}>
                <option value="A">Team A</option>
                <option value="B">Team B</option>
              </select>
            </div>
            <button type="button" className="primary" disabled={!canRun} onClick={run}>
              {match.status === "loading" ? "Running match..." : "Run match"}
            </button>
          </section>

          {specsError && <p role="alert" className="error">Could not load settings: {specsError}</p>}
          {match.status === "error" && <p role="alert" className="error">{match.message}</p>}
          {replay?.duration.clamped && (
            <p className="muted">Requested {replay.duration.requested} minutes; matches are capped at {replay.duration.effective}.</p>
          )}

          <Scoreboard snapshot={snapshot} />
          <Pitch snapshot={snapshot} />

          <div className="playback">
            <button type="button" disabled={!replay} onClick={pb.toggle}>{pb.playing ? "Pause" : "Play"}</button>
            <label>
              Speed{" "}
              <select value={pb.speed} onChange={(e) => pb.setSpeed(Number(e.target.value))}>
                {[1, 2, 4, 8].map((v) => <option key={v} value={v}>{v}x</option>)}
              </select>
            </label>
            <input
              type="range"
              min={0}
              max={1000}
              value={duration > 0 ? Math.round((pb.time / duration) * 1000) : 0}
              disabled={!replay}
              aria-label="Replay position"
              onChange={(e) => pb.seek((Number(e.target.value) / 1000) * duration)}
            />
          </div>
          {replay && (
            <p className="muted">
              Result: {replay.result.score_a} to {replay.result.score_b}, ended by {replay.result.reason.toLowerCase().replaceAll("_", " ")}.
            </p>
          )}
        </div>

        <div>
          {specs.length > 0 && (
            <SettingsPanel specs={specs} values={values} onChange={(k, t) => setValues((v) => ({ ...v, [k]: t }))} onReset={() => resetValues(specs)} />
          )}
          <EventLog events={replay?.events ?? []} time={pb.time} onJump={pb.seek} />
        </div>
      </div>
    </main>
  );
}
