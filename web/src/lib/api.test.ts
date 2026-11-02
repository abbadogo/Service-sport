import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError, fetchSettings, fetchSquads, runMatch } from "./api";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("fetchSettings", () => {
  it("returns the settings list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ settings: [{ key: "a" }] })));
    await expect(fetchSettings()).resolves.toEqual([{ key: "a" }]);
  });

  it("turns a network failure into a readable error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(fetchSettings()).rejects.toMatchObject({ code: "network", message: expect.stringContaining("Cannot reach") });
  });

  it("times out when the server never answers", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_, reject) => init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))),
      ),
    );
    const done = expect(fetchSettings()).rejects.toMatchObject({ code: "timeout" });
    await vi.advanceTimersByTimeAsync(15_001);
    await done;
  });
});

describe("runMatch", () => {
  it("surfaces the server's error message and code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ error: { code: "invalid_minutes", message: "bad minutes" } }, 400)));
    const err = await runMatch({ minutes: 0 }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err).toMatchObject({ code: "invalid_minutes", message: "bad minutes", status: 400 });
  });

  it("falls back to a generic message when the error body is not shaped as expected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({}, 502)));
    await expect(runMatch({})).rejects.toMatchObject({ code: "http_error", message: "Server error (502)" });
  });

  it("rejects a response that is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>oops</html>", { status: 200 })));
    await expect(runMatch({})).rejects.toMatchObject({ code: "bad_response" });
  });

  it("rejects a replay with the wrong layout", async () => {
    const replay = { schema: { head: [], player_fields: [], phases: {} }, players: [], frames: [[0]], events: [] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(replay)));
    await expect(runMatch({})).rejects.toMatchObject({ code: "bad_response" });
  });

  it("posts the request as JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({}, 400));
    vi.stubGlobal("fetch", fetchMock);
    await runMatch({ minutes: 2, seed: 5 }).catch(() => undefined);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/matches");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ minutes: 2, seed: 5 });
  });
});

describe("fetchSquads", () => {
  it("returns the squads with their players and ratings", async () => {
    const squad = {
      id: "kano_stars",
      name: "Kano Stars",
      overall: 62,
      players: [
        {
          name: "Umar Jibrin",
          shirt: 1,
          overall: 64,
          pace: 50,
          power: 62,
          accuracy: 70,
          endurance: 72,
          reach: 66,
        },
      ],
    };
    const reply = new Response(JSON.stringify({ squads: [squad] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply));
    await expect(fetchSquads()).resolves.toEqual([squad]);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("turns a network failure into a readable error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(fetchSquads()).rejects.toMatchObject({ code: "network" });
  });
});
