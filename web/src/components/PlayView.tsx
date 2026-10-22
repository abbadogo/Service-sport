import { useCallback, useEffect, useRef, useState } from "react";
import { isMoveKey, keysToVector, strongest, updateAim } from "../lib/input";
import type { Snapshot } from "../lib/replay";
import { validateMinutes } from "../lib/settings";
import { usePlay } from "../lib/usePlay";
import type { Controls, Vec } from "../types";
import { EventLog } from "./EventLog";
import { Joystick } from "./Joystick";
import { Pitch } from "./Pitch";
import { Scoreboard } from "./Scoreboard";
import { StrikeButton } from "./StrikeButton";

/** Play a live match as Team A: you drive the player nearest the disc, the computer plays the rest. */
export function PlayView() {
  const keys = useRef(new Set<string>());
  const stick = useRef<Vec>([0, 0]);
  const touchCharge = useRef(false);
  const aim = useRef<Vec>([1, 0]);
  const [minutes, setMinutes] = useState("2");
  const [snap, setSnap] = useState<Snapshot | null>(null);

  const getControls = useCallback((): Controls => {
    const move = strongest(keysToVector(keys.current), stick.current);
    aim.current = updateAim(aim.current, move);
    return { move, aim: aim.current, charge: touchCharge.current || keys.current.has("Space") };
  }, []);

  const { status, error, events, side, result, start, stop, snapshot } = usePlay(getControls);
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

  const minutesError = validateMinutes(minutes);
  const busy = status === "starting" || playing;
  const me = snap?.players.find((p) => p.isCursor && p.team === side);

  return (
    <div className="layout">
      <div>
        <section className="card controls" aria-label="Match options">
          <div className="field">
            <label htmlFor="play-minutes">Minutes (max 15)</label>
            <input id="play-minutes" value={minutes} onChange={(e) => setMinutes(e.target.value)} inputMode="decimal" aria-invalid={minutesError !== null} />
            {minutesError && <small role="alert" className="error">{minutesError}</small>}
          </div>
          <button
            type="button"
            className="primary"
            disabled={busy || minutesError !== null}
            onClick={() => start({ side: "A", minutes: Number(minutes), seed: Math.floor(Math.random() * 1_000_000) })}
          >
            {status === "starting" ? "Starting..." : "Start match"}
          </button>
          {playing && <button type="button" onClick={stop}>Stop</button>}
        </section>

        {error && <p role="alert" className="error">{error}</p>}
        {status === "over" && result && (
          <p role="status">Full time: {result.score_a} to {result.score_b}, ended by {result.reason.toLowerCase().replaceAll("_", " ")}.</p>
        )}

        <Scoreboard snapshot={snap} />
        <Pitch snapshot={snap} />
        <p className="muted">
          {me ? `You are ${me.id} (the ringed player). ` : ""}Move: WASD, arrow keys or the stick. Hold SPACE or the button to charge the power
          bar, release to hit. A full bar is a long hit. Serves are automatic in this version.
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
