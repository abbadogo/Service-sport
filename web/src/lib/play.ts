import type { Controls, MatchRequest, PlayStart, PlayStep } from "../types";
import { ApiRequestError, request } from "./api";
import { frameWidth } from "./replay";

const JSON_HEADERS = { "Content-Type": "application/json" };

function checkFrame(frame: unknown, players: number): void {
  if (!Array.isArray(frame) || frame.length !== frameWidth(players)) {
    throw new ApiRequestError("The server sent a frame this app cannot read.", "bad_response");
  }
}

export async function startPlay(req: MatchRequest, signal?: AbortSignal): Promise<PlayStart> {
  const start = await request<PlayStart>(
    "/api/play",
    { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(req) },
    15_000,
    signal,
  );
  checkFrame(start.frame, start.players?.length ?? 0);
  return start;
}

export async function stepPlay(
  session: string,
  controls: Controls,
  players: number,
  signal?: AbortSignal,
): Promise<PlayStep> {
  const step = await request<PlayStep>(
    `/api/play/${encodeURIComponent(session)}/step`,
    { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(controls) },
    5_000,
    signal,
  );
  checkFrame(step.frame, players);
  return step;
}

/** Tell the server the match is over. Failing to is harmless (idle matches expire), but we log it. */
export function endPlay(session: string): void {
  fetch(`/api/play/${encodeURIComponent(session)}`, { method: "DELETE", keepalive: true }).catch((err) => {
    console.warn("could not end the live match", err);
  });
}
