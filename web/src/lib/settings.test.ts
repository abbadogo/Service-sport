import { describe, expect, it } from "vitest";
import type { SettingSpec } from "../types";
import { changedSettings, validateMinutes, validateSeed, validateSetting } from "./settings";

const spec: SettingSpec = { key: "k", group: "g", label: "L", description: "d", minimum: 0, maximum: 0.4, step: 0.01, default: 0.06 };

describe("validateSetting", () => {
  it("accepts values in range, including the limits", () => {
    for (const v of ["0", "0.06", "0.4"]) expect(validateSetting(spec, v)).toBeNull();
  });
  it("rejects out-of-range and non-numeric text", () => {
    expect(validateSetting(spec, "0.5")).toMatch(/between/);
    expect(validateSetting(spec, "-0.1")).toMatch(/between/);
    for (const v of ["", "abc", "1e3", "0,5"]) expect(validateSetting(spec, v)).toBe("Enter a number");
  });
});

describe("validateMinutes / validateSeed", () => {
  it("minutes", () => {
    expect(validateMinutes("2")).toBeNull();
    expect(validateMinutes("0.5")).toBeNull();
    expect(validateMinutes("0")).toMatch(/more than 0/);
    expect(validateMinutes("16")).toMatch(/capped/);
    expect(validateMinutes("x")).toMatch(/number/);
  });
  it("seed", () => {
    expect(validateSeed("42")).toBeNull();
    expect(validateSeed("-1")).not.toBeNull();
    expect(validateSeed("1.5")).not.toBeNull();
    expect(validateSeed("99999999999")).toBe("Too large");
  });
});

describe("changedSettings", () => {
  it("sends only values that differ from the defaults", () => {
    const other: SettingSpec = { ...spec, key: "o", default: 1, minimum: 0, maximum: 2 };
    expect(changedSettings([spec, other], { k: "0.06", o: "1.5" })).toEqual({ o: 1.5 });
  });
});
