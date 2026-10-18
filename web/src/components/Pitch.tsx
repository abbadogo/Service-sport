import { useEffect, useRef, useState } from "react";
import { PITCH_L, PITCH_W, drawScene } from "../lib/draw";
import type { Snapshot } from "../lib/replay";

export function Pitch({ snapshot }: { snapshot: Snapshot | null }) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(800);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const c = canvas.current;
    const ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = width * dpr;
    c.height = ((width * PITCH_W) / PITCH_L) * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawScene(ctx, snapshot, width);
  }, [snapshot, width]);

  return (
    <div ref={wrap} className="pitch">
      <canvas
        ref={canvas}
        role="img"
        aria-label="Top-down view of the pitch showing both teams and the ball"
        style={{ width: "100%", height: (width * PITCH_W) / PITCH_L }}
      />
    </div>
  );
}
