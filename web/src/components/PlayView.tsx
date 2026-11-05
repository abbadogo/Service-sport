import { useCallback, useEffect, useRef, useState } from "react";
import { fetchSquads } from "../lib/api";
import { isMoveKey, keysToVector, strongest } from "../lib/input";
import type { Snapshot } from "../lib/replay";
import { validateMinutes } from "../lib/settings";
import { usePlay } from "../lib/usePlay";
import type { Controls, MatchRequest, Squad, Vec } from "../types";
import { EventLog } from "./EventLog";
import { Joystick } from "./Joystick";
import { Pitch } from "./Pitch";
import { Scoreboard } from "./Scoreboard";
import { SquadPanel } from "./SquadPanel";
import { StrikeButton } from "./StrikeButton";

/** Play a live match as Team A: you drive the player nearest the disc, the computer plays the rest. */
export function PlayView() {
  const keys = useRef(new Set<string>());
  const stick = useRef<Vec>([0, 0]);
  const touchCharge = useRef(false);
  const [minutes, setMinutes] = useState("2");
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [squads, setSquads] = useState<Squad[]>([]);
  const [squadA, setSquadA] = useState("");
  const [squadB, setSquadB] = useState("");

  // The squad list is optional: without it the game still starts with random players.
  useEffect(() => {
    const ctl = new AbortController();
    fetchSquads(ctl.signal).then(setSquads, () => undefined);
    return () => ctl.abort();
  }, []);

  const getControls = useCallback((): Controls => {
    const move = strongest(keysToVector(keys.current), stick.current);
    // The hit goes straight at the other team; pushing up or down as you release angles it.
    return { move, aim: move, charge: touchCharge.current || keys.current.has("Space") };
  }, []);

  const { status, error, events, side, result, start, stop, snapshot, roster } = usePlay(getControls);
  const playing = status === "playing";

  useEffect(() => {
    if (!playing) return;
    const down = (e: KeyboardEvent) => {
      if (isMoveKey(e.code) || e.code === "Space") {
        e.preventDefault();
        keys.current.add(e.code);
      }
    };
    const up = (e: KeyboardEvent) => keys.current.delete(e.code);
    const clear = () => keys.current.clear();
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", clear);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", clear);
      clear();
    };
  }, [playing]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const tick = () => {
      setSnap(snapshot());
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, snapshot]);

  const matchRequest = (): MatchRequest => ({
    side: "A",
    minutes: Number(minutes),
    seed: Math.floor(Math.random() * 1_000_000),
    ...(squadA ? { squad_a: squadA } : {}),
    ...(squadB ? { squad_b: squadB } : {}),
  });

  const minutesError = validateMinutes(minutes);
  const busy = status === "starting" || playing;
  const me = snap?.players.find((p) => p.isCursor && p.team === side);

  return (
    <div className="layout">
      <div>
        <section className="card controls" aria-label="Match options">
          {squads.length > 0 && (
            <>
              <div className="field">
                <label htmlFor="play-squad-a">Your squad</label>
                <select id="play-squad-a" value={squadA} onChange={(e) => setSquadA(e.target.value)}>
                  <option value="">Random players</option>
                  {squads.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.overall})
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="play-squad-b">Opponent squad</label>
                <select id="play-squad-b" value={squadB} onChange={(e) => setSquadB(e.target.value)}>
                  <option value="">Random players</option>
                  {squads.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.overall})
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
          <div className="field">
            <label htmlFor="play-minutes">Minutes (max 15)</label>
            <input id="play-minutes" value={minutes} onChange={(e) => setMinutes(e.target.value)} inputMode="decimal" aria-invalid={minutesError !== null} />
            {minutesError && <small role="alert" className="error">{minutesError}</small>}
          </div>
          <button
            type="button"
            className="primary"
            disabled={busy || minutesError !== null}
            onClick={() => start(matchRequest())}
          >
            {status === "starting" ? "Starting..." : "Start match"}
          </button>
          {playing && <button type="button" onClick={stop}>Stop</button>}
        </section>

        <SquadPanel roster={roster} side={side} />
        {error && <p role="alert" className="error">{error}</p>}
        {status === "over" && result && (
          <p role="status">Full time: {result.score_a} to {result.score_b}, ended by {result.reason.toLowerCase().replaceAll("_", " ")}.</p>
        )}

        <Scoreboard snapshot={snap} roster={roster} />
        <Pitch snapshot={snap} />
        <p className="muted">
          {me ? `You are ${me.id} (the ringed player). ` : ""}Move: WASD, arrow keys or the stick. Hold SPACE or the button to charge the power
          bar, release to hit: the disc goes straight at the other team, and pushing up or down as you release angles it.
          A full bar is a long hit. Serves are automatic in this version.
        </p>

        <div className="pad">
          <Joystick onChange={(v) => { stick.current = v; }} />
          <StrikeButton level={me?.power ?? 0} onChange={(held) => { touchCharge.current = held; }} />
        </div>
      </div>
      <div>
        <EventLog events={events} time={snap?.t ?? 0} onJump={() => undefined} />
      </div>
    </div>
  );
}
