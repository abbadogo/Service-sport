export interface SettingSpec {
  key: string;
  group: string;
  label: string;
  description: string;
  minimum: number;
  maximum: number;
  step: number;
  default: number;
}

export interface ReplayEvent {
  t: number;
  kind: "point" | "serve" | "mishit" | "longhit" | "rotate" | "sd" | "end";
  text: string;
}

export interface Replay {
  schema: { head: string[]; player_fields: string[]; phases: Record<string, number> };
  players: string[];
  frames: number[][];
  events: ReplayEvent[];
  result: {
    score_a: number;
    score_b: number;
    winner: "A" | "B" | null;
    reason: string;
    sim_time_s: number;
    live_time_s: number;
  };
  duration: { requested: number | null; effective: number; clamped: boolean };
}

export interface MatchRequest {
  side?: "A" | "B"; // live play: the team you control
  minutes?: number;
  seed?: number;
  opening_server?: "A" | "B";
  settings?: Record<string, number>;
}

export interface PlayStart {
  session: string;
  side: "A" | "B";
  schema: Replay["schema"];
  players: string[];
  frame: number[];
}

export interface PlayStep {
  frame: number[];
  events: ReplayEvent[];
  finished: boolean;
  ticks: number;
  result?: Replay["result"];
}

export type Vec = [number, number];

/** What the player is doing right now (sent to the server several times a second). */
export interface Controls {
  move: Vec;
  aim: Vec;
  charge: boolean;
}
