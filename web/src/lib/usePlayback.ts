import { useCallback, useEffect, useRef, useState } from "react";

export function usePlayback(duration: number) {
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(2);
  const timeRef = useRef(0);

  const seek = useCallback((t: number) => {
    timeRef.current = t;
    setTime(t);
  }, []);

  // A new replay starts from the beginning.
  useEffect(() => {
    seek(0);
    setPlaying(true);
  }, [duration, seek]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last: number | null = null;
    const tick = (ts: number) => {
      if (last !== null) {
        const next = Math.min(duration, timeRef.current + ((ts - last) / 1000) * speed);
        seek(next);
        if (next >= duration) setPlaying(false);
      }
      last = ts;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, duration, seek]);

  const toggle = useCallback(() => {
    if (timeRef.current >= duration) seek(0);
    setPlaying((p) => !p);
  }, [duration, seek]);

  return { time, playing, speed, setSpeed, seek, toggle };
}
