import type { MatchRequest, Replay, SettingSpec } from "../types";
import { validateReplay } from "./replay";

export class ApiRequestError extends Error {
  constructor(message: string, readonly code: string, readonly status?: number) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function request<T>(path: string, init: RequestInit, timeoutMs: number, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  signal?.addEventListener("abort", () => controller.abort());

  let res: Response;
  try {
    res = await fetch(path, { ...init, signal: controller.signal });
  } catch (err) {
    if (timedOut) throw new ApiRequestError("The server took too long to answer.", "timeout");
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiRequestError("Cannot reach the server. Is it running?", "network");
  } finally {
    clearTimeout(timer);
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch {
    throw new ApiRequestError("The server sent a response this app cannot read.", "bad_response", res.status);
  }
  if (!res.ok) {
    const e = (body as { error?: { code?: string; message?: string } }).error;
    throw new ApiRequestError(e?.message ?? `Server error (${res.status})`, e?.code ?? "http_error", res.status);
  }
  return body as T;
}

export async function fetchSettings(signal?: AbortSignal): Promise<SettingSpec[]> {
  const r = await request<{ settings: SettingSpec[] }>("/api/settings", {}, 15_000, signal);
  return r.settings;
}

export async function runMatch(req: MatchRequest, signal?: AbortSignal): Promise<Replay> {
  const replay = await request<Replay>(
    "/api/matches",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) },
    120_000,
    signal,
  );
  try {
    validateReplay(replay);
  } catch (err) {
    throw new ApiRequestError(err instanceof Error ? err.message : "invalid replay", "bad_response");
  }
  return replay;
}
