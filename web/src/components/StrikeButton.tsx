interface Props {
  level: number; // the power bar, 0..1
  onChange: (held: boolean) => void;
}

/** Hold to charge the power bar, release to strike. */
export function StrikeButton({ level, onChange }: Props) {
  const pct = Math.round(Math.min(1, Math.max(0, level)) * 100);
  return (
    <div className="strike">
      <div className="meter" role="progressbar" aria-label="Power bar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        <i style={{ width: `${pct}%` }} className={pct >= 90 ? "full" : ""} />
      </div>
      <button
        type="button"
        className="hit"
        aria-label="Strike: hold to charge, release to hit"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture?.(e.pointerId);
          onChange(true);
        }}
        onPointerUp={() => onChange(false)}
        onPointerCancel={() => onChange(false)}
        onContextMenu={(e) => e.preventDefault()}
      >
        HOLD
        <small>release to hit</small>
      </button>
    </div>
  );
}
