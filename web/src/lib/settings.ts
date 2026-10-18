import type { SettingSpec } from "../types";

const NUMBER = /^-?\d+(\.\d+)?$/;

/** Returns an error message, or null when the text is a valid value for the spec. */
export function validateSetting(spec: SettingSpec, text: string): string | null {
  if (!NUMBER.test(text.trim())) return "Enter a number";
  const v = Number(text);
  if (v < spec.minimum || v > spec.maximum) return `Must be between ${spec.minimum} and ${spec.maximum}`;
  return null;
}

export function validateMinutes(text: string): string | null {
  if (!NUMBER.test(text.trim())) return "Enter a number of minutes";
  const v = Number(text);
  if (v <= 0) return "Must be more than 0";
  if (v > 15) return "Longer than 15 minutes is capped at 15";
  return null;
}

export function validateSeed(text: string): string | null {
  if (!/^\d+$/.test(text.trim())) return "Enter a whole number";
  return Number(text) > 2147483647 ? "Too large" : null;
}

/** Only the settings that differ from the server defaults are sent. */
export function changedSettings(specs: SettingSpec[], values: Record<string, string>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const s of specs) {
    const v = Number(values[s.key]);
    if (v !== s.default) out[s.key] = v;
  }
  return out;
}
