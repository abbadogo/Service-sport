import type { Snapshot } from "./replay";

export const PITCH_L = 105;
export const PITCH_W = 68;
const TEAM_COLOR = { A: "#1f5fbf", B: "#d6336c" } as const;

/** Draw the pitch and a snapshot. The context must already be scaled to CSS pixels. */
export function drawScene(ctx: CanvasRenderingContext2D, snap: Snapshot | null, width: number): void {
  const s = width / PITCH_L;
  ctx.clearRect(0, 0, width, PITCH_W * s);
  for (let c = 0; c < 15; c++) {
    ctx.fillStyle = c % 2 ? "#3a7d3d" : "#337636";
    ctx.fillRect(c * 7 * s, 0, 7 * s, PITCH_W * s);
  }
  ctx.fillStyle = "rgba(31,95,191,0.10)";
  ctx.fillRect(0, 0, (PITCH_L / 2) * s, PITCH_W * s);
  ctx.fillStyle = "rgba(214,51,108,0.10)";
  ctx.fillRect((PITCH_L / 2) * s, 0, (PITCH_L / 2) * s, PITCH_W * s);

  ctx.strokeStyle = "rgba(255,255,255,0.85)";
  ctx.lineWidth = Math.max(1.5, s * 0.18);
  ctx.strokeRect(0, 0, PITCH_L * s, PITCH_W * s);
  ctx.setLineDash([s * 1.2, s * 0.9]);
  ctx.beginPath();
  ctx.moveTo((PITCH_L / 2) * s, 0);
  ctx.lineTo((PITCH_L / 2) * s, PITCH_W * s);
  ctx.stroke();
  ctx.setLineDash([]);
  if (!snap) return;

  for (const p of snap.players) {
    const x = p.x * s;
    const y = p.y * s;
    ctx.fillStyle = TEAM_COLOR[p.team];
    ctx.beginPath();
    ctx.arc(x, y, s * 1.1, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = s * 0.2;
    ctx.stroke();
    if (p.isCursor) {
      ctx.strokeStyle = "#ffe066";
      ctx.lineWidth = s * 0.35;
      ctx.beginPath();
      ctx.arc(x, y, s * 2.1, 0, Math.PI * 2);
      ctx.stroke();
    }
    // stamina bar under the player, strike power bar above
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(x - s * 1.4, y + s * 1.5, s * 2.8, s * 0.5);
    ctx.fillStyle = p.stamina < 0.2 ? "#ff5a4d" : p.stamina < 0.45 ? "#ffc23d" : "#8be28b";
    ctx.fillRect(x - s * 1.4, y + s * 1.5, s * 2.8 * p.stamina, s * 0.5);
    if (p.power > 0.02) {
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(x - s * 1.6, y - s * 2.1, s * 3.2, s * 0.6);
      ctx.fillStyle = p.power > 0.85 ? "#ff4d4d" : p.power > 0.5 ? "#ffb02e" : "#ffe066";
      ctx.fillRect(x - s * 1.6, y - s * 2.1, s * 3.2 * p.power, s * 0.6);
    }
    ctx.fillStyle = "#fff";
    ctx.font = `bold ${Math.max(9, s * 1.05)}px system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(p.id, x, y);
  }

  const b = snap.ball;
  if (b) {
    // A thin bar when upright, a full disc when flat.
    const x = b.x * s;
    const y = b.y * s;
    const tilt = (b.tilt * Math.PI) / 180;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(Math.atan2(b.hy, b.hx));
    ctx.beginPath();
    ctx.ellipse(0, 0, (s * 1.7) / 2, (s * (0.35 + 1.35 * Math.sin(tilt))) / 2, 0, 0, Math.PI * 2);
    ctx.fillStyle = b.flat ? "#ff9f1c" : "#ffd43b";
    ctx.fill();
    ctx.strokeStyle = "#222";
    ctx.lineWidth = s * 0.15;
    ctx.stroke();
    ctx.restore();
    if (b.flat) {
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = s * 0.2;
      ctx.beginPath();
      ctx.arc(x, y, s * 1.6, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
}
