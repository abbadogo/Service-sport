import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StrikeButton } from "./StrikeButton";

describe("StrikeButton", () => {
  it("reports holding and releasing", () => {
    const onChange = vi.fn();
    render(<StrikeButton level={0} onChange={onChange} />);
    const button = screen.getByRole("button", { name: /strike/i });
    fireEvent.pointerDown(button);
    expect(onChange).toHaveBeenLastCalledWith(true);
    fireEvent.pointerUp(button);
    expect(onChange).toHaveBeenLastCalledWith(false);
    fireEvent.pointerDown(button);
    fireEvent.pointerCancel(button);
    expect(onChange).toHaveBeenLastCalledWith(false);
  });

  it("shows the power bar level, clamped to 0 to 100", () => {
    const { rerender } = render(<StrikeButton level={0.42} onChange={() => undefined} />);
    expect(screen.getByRole("progressbar", { name: "Power bar" })).toHaveAttribute("aria-valuenow", "42");
    rerender(<StrikeButton level={3} onChange={() => undefined} />);
    expect(screen.getByRole("progressbar", { name: "Power bar" })).toHaveAttribute("aria-valuenow", "100");
    rerender(<StrikeButton level={-1} onChange={() => undefined} />);
    expect(screen.getByRole("progressbar", { name: "Power bar" })).toHaveAttribute("aria-valuenow", "0");
  });
});
