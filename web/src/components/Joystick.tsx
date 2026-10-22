import { useRef, useState, type PointerEvent } from "react";
import { stickVector } from "../lib/input";
import type { Vec } from "../types";

/** A touch stick. Reports a vector inside the unit circle; [0, 0] when released. */
export function Joystick({ onChange }: { onChange: (v: Vec) => void }) {
  const base = useRef<HTMLDivElement>(null);
  const active = useRef<number | null>(null);
  const [knob, setKnob] = useState<Vec>([0, 0]);

  const update = (e: PointerEvent<HTMLDivElement>) => {
    const el = base.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const radius = r.width / 2;
    const v = stickVector(e.clientX - (r.left + radius), e.clientY - (r.top + radius), radius);
    setKnob(v);
    onChange(v);
  };
  const release = () => {
    active.current = null;
    setKnob([0, 0]);
    onChange([0, 0]);
  };

  return (
    <div
      ref={base}
      className="stick"
      role="group"
      aria-label="Movement stick: drag to run"
      onPointerDown={(e) => {
        active.current = e.pointerId;
        e.currentTarget.setPointerCapture?.(e.pointerId);
        update(e);
      }}
      onPointerMove={(e) => {
        if (active.current === e.pointerId) update(e);
      }}
      onPointerUp={release}
      onPointerCancel={release}
    >
      <div className="knob" style={{ transform: `translate(${knob[0] * 40}px, ${knob[1] * 40}px)` }} />
    </div>
  );
}
