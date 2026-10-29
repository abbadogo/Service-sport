import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePlayback } from "./usePlayback";

let frame: ((ts: number) => void) | null = null;
const cancel = vi.fn();

beforeEach(() => {
  frame = null;
  vi.stubGlobal("requestAnimationFrame", (f: (ts: number) => void) => {
    frame = f;
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", cancel);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

const tick = (ts: number) => act(() => frame?.(ts));

describe("usePlayback", () => {
  it("starts playing from 0 at speed 2", () => {
    const { result } = renderHook(() => usePlayback(10));
    expect(result.current.time).toBe(0);
    expect(result.current.playing).toBe(true);
    expect(result.current.speed).toBe(2);
  });

  it("advances by elapsed seconds times speed", () => {
    const { result } = renderHook(() => usePlayback(10));
    tick(0);
    expect(result.current.time).toBe(0);
    tick(1000);
    expect(result.current.time).toBe(2);
  });

  it("uses the new speed after setSpeed", () => {
    const { result } = renderHook(() => usePlayback(10));
    act(() => result.current.setSpeed(1));
    tick(0);
    tick(1000);
    expect(result.current.time).toBe(1);
  });

  it("stops at the end and clamps time to the duration", () => {
    const { result } = renderHook(() => usePlayback(3));
    tick(0);
    tick(2000);
    expect(result.current.time).toBe(3);
    expect(result.current.playing).toBe(false);
  });

  it("seek jumps to the given time", () => {
    const { result } = renderHook(() => usePlayback(10));
    act(() => result.current.seek(4));
    expect(result.current.time).toBe(4);
  });

  it("toggle pauses and cancels the pending frame", () => {
    const { result } = renderHook(() => usePlayback(10));
    act(() => result.current.toggle());
    expect(result.current.playing).toBe(false);
    expect(cancel).toHaveBeenCalled();
  });

  it("toggle at the end restarts from 0 and plays", () => {
    const { result } = renderHook(() => usePlayback(3));
    tick(0);
    tick(2000);
    expect(result.current.playing).toBe(false);
    act(() => result.current.toggle());
    expect(result.current.time).toBe(0);
    expect(result.current.playing).toBe(true);
  });

  it("restarts from the beginning when the duration changes", () => {
    const { result, rerender } = renderHook(({ d }) => usePlayback(d), {
      initialProps: { d: 10 },
    });
    act(() => result.current.seek(5));
    rerender({ d: 20 });
    expect(result.current.time).toBe(0);
    expect(result.current.playing).toBe(true);
  });

  it("cancels the frame on unmount", () => {
    const { unmount } = renderHook(() => usePlayback(10));
    unmount();
    expect(cancel).toHaveBeenCalled();
  });
});
