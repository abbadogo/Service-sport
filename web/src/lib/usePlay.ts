import { useCallback, useEffect, useRef, useState } from "react";
import type { Controls, MatchRequest, Replay, ReplayEvent } from "../types";
import { ApiRequestError } from "./api";
import { endPlay, startPlay, stepPlay } from "./play";
import { H, blendFrames, type Snapshot } from "./replay";

export type PlayStatus = "idle" | "starting" | "playing" | "over" | "error";

interface FrameBuffer {
  prev: number[];
  curr: number[];
  currAt: number; // when `curr` arrived (ms)
  interval: number; // how long the last update took to arrive (ms)
}

const STEP_EVERY_MS = 50;
const MAX_EVENTS = 40;

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const id = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => { clearTimeout(id); resolve(); }, { once: true });
  });

const messageOf = (err: unknown) =>
  err instanceof ApiRequestError || err instanceof Error ? err.message : "Unexpected error";

/** Runs a live match: sends the controls about 20 times a second and keeps the latest two frames to draw between. */
export function usePlay(getControls: () => Controls) {
  const [status, setStatus] = useState<PlayStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<ReplayEvent[]>([]);
  const [side, setSide] = useState<"A" | "B">("A");
  const [result, setResult] = useState<Replay["result"] | null>(null);
  const buffer = useRef<FrameBuffer | null>(null);
  const players = useRef<string[]>([]);
  const abort = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    abort.current?.abort();
    abort.current = null;
    setStatus("idle");
  }, []);
  useEffect(() => stop, [stop]);

  const start = useCallback(
    async (req: MatchRequest) => {
      stop();
      const controller = new AbortController();
      abort.current = controller;
      setStatus("starting");
      setError(null);
      setEvents([]);
      setResult(null);
      let session: string | null = null;
      try {
        const s = await startPlay(req, controller.signal);
        session = s.session;
        players.current = s.players;
        setSide(s.side);
        buffer.current = { prev: s.frame, curr: s.frame, currAt: performance.now(), interval: STEP_EVERY_MS };
        setStatus("playing");
        while (!controller.signal.aborted) {
          const started = performance.now();
          const r = await stepPlay(s.session, getControls(), s.players.length, controller.signal);
          const now = performance.now();
          const old: FrameBuffer | null = buffer.current;
          buffer.current = {
            prev: old ? old.curr : r.frame,
            curr: r.frame,
            currAt: now,
            interval: Math.max(16, old ? now - old.currAt : STEP_EVERY_MS),
          };
          if (r.events.length > 0) setEvents((prev) => [...prev, ...r.events].slice(-MAX_EVENTS));
          if (r.finished) {
            setResult(r.result ?? null);
            setStatus("over");
            break;
          }
          await sleep(Math.max(0, STEP_EVERY_MS - (performance.now() - started)), controller.signal);
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(messageOf(err));
        setStatus("error");
      } finally {
        if (session) endPlay(session);
      }
    },
    [getControls, stop],
  );

  /** The picture right now: the last two frames blended by how long ago the newest one arrived. */
  const snapshot = useCallback((): Snapshot | null => {
    const b = buffer.current;
    if (!b) return null;
    const k = Math.min(1, Math.max(0, (performance.now() - b.currAt) / b.interval));
    return blendFrames(players.current, b.prev, b.curr, k, b.curr[H.T]);
  }, []);

  return { status, error, events, side, result, start, stop, snapshot };
}
