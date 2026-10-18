import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SettingSpec } from "../types";
import { SettingsPanel } from "./SettingsPanel";

const specs: SettingSpec[] = [
  { key: "bevel", group: "Ball", label: "Bevel strength", description: "Sideways pull.", minimum: 0, maximum: 0.02, step: 0.0005, default: 0.0015 },
  { key: "mishit", group: "Strikes", label: "Base mishit chance", description: "Chance to mishit.", minimum: 0, maximum: 0.4, step: 0.01, default: 0.06 },
];

const toggle: SettingSpec = { key: "rotation", group: "Rules", label: "Rotate positions", description: "On or off.", minimum: 0, maximum: 1, step: 1, default: 1 };

describe("SettingsPanel", () => {
  it("shows on/off rules as checkboxes and reports changes as 1 or 0", () => {
    const onChange = vi.fn();
    render(<SettingsPanel specs={[toggle]} values={{ rotation: "1" }} onChange={onChange} onReset={() => {}} />);
    const box = screen.getByLabelText("Rotate positions");
    expect(box).toBeChecked();
    fireEvent.click(box);
    expect(onChange).toHaveBeenCalledWith("rotation", "0");
  });

  it("groups settings and labels every input", () => {
    render(<SettingsPanel specs={specs} values={{}} onChange={() => {}} onReset={() => {}} />);
    expect(screen.getByRole("group", { name: "Ball" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Strikes" })).toBeInTheDocument();
    expect(screen.getByLabelText("Bevel strength")).toHaveValue(0.0015); // falls back to the default
  });

  it("flags an out-of-range value and marks the input invalid", () => {
    render(<SettingsPanel specs={specs} values={{ mishit: "0.9" }} onChange={() => {}} onReset={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/between 0 and 0.4/);
    expect(screen.getByLabelText("Base mishit chance")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Bevel strength")).toHaveAttribute("aria-invalid", "false");
  });

  it("reports edits and reset clicks", () => {
    const onChange = vi.fn();
    const onReset = vi.fn();
    render(<SettingsPanel specs={specs} values={{}} onChange={onChange} onReset={onReset} />);
    fireEvent.change(screen.getByLabelText("Base mishit chance"), { target: { value: "0.2" } });
    expect(onChange).toHaveBeenCalledWith("mishit", "0.2");
    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(onReset).toHaveBeenCalledOnce();
  });
});
