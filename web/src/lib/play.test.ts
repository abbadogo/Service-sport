import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError } from "./api";
import { endPlay, startPlay, stepPlay } from "./play";
import { frameWidth } from "./replay";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const frame = (players: number) => new Array<number>(frameWidth(players)).fill(0);
const controls = { move: [1, 0] as [number, number], aim: [1, 0] as [number, number], charge: true };

afterEach(() => vi.unstubAllGlobals());

describe("startPlay", () => {
  it("returns the session and checks the first frame", async () => {
    const body = { session: "abc", side: "A", schema: {}, players: ["A1", "B1"], frame: frame(2) };
    const fetchMock = vi.fn().mockResolvedValue(json(body));
    vi.stubGlobal("fetch", fetchMock);
    await expect(startPlay({ side: "A", minutes: 2 })).resolves.toMatchObject({ session: "abc" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/play");
    expect(JSON.parse(init.body as string)).toEqual({ side: "A", minutes: 2 });
  });

  it("rejects a frame of the wrong size", async () => {
    const body = { session: "abc", side: "A", schema: {}, players: ["A1", "B1"], frame: [1, 2, 3] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(body)));
    await expect(startPlay({})).rejects.toMatchObject({ code: "bad_response" });
  });

  it("surfaces the server's message when it is busy", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ error: { code: "busy", message: "too many" } }, 503)));
    const err = await startPlay({}).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err).toMatchObject({ code: "busy", message: "too many", status: 503 });
  });
});

describe("stepPlay", () => {
  it("posts the controls and returns the new frame", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ frame: frame(2), events: [], finished: false, ticks: 6 }));
    vi.stubGlobal("fetch", fetchMock);
    const r = await stepPlay("s/1", controls, 2);
    expect(r.ticks).toBe(6);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/play/s%2F1/step"); // the id is escaped
    expect(JSON.parse(init.body as string)).toEqual(controls);
  });

  it("rejects a frame that does not match the player count", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ frame: frame(3), events: [], finished: false, ticks: 1 })));
    await expect(stepPlay("abc", controls, 2)).rejects.toMatchObject({ code: "bad_response" });
  });

  it("reports an expired match", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ error: { code: "no_such_match", message: "expired" } }, 404)));
    await expect(stepPlay("abc", controls, 2)).rejects.toMatchObject({ code: "no_such_match", status: 404 });
  });
});

describe("endPlay", () => {
  it("sends a DELETE and logs instead of throwing if that fails", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    expect(() => endPlay("abc")).not.toThrow();
    await Promise.resolve();
    await Promise.resolve();
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});
