import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Joystick } from "./Joystick";

class FakePointerEvent extends MouseEvent {
  pointerId: number;
  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 0;
  }
}
(window as unknown as { PointerEvent: unknown }).PointerEvent = FakePointerEvent;

afterEach(cleanup);

function setup() {
  const onChange = vi.fn();
  const { container } = render(<Joystick onChange={onChange} />);
  const stick = screen.getByRole("group");
  stick.getBoundingClientRect = () =>
    ({ left: 0, top: 0, width: 100, height: 100, right: 100, bottom: 100, x: 0, y: 0 }) as DOMRect;
  const knob = container.querySelector(".knob") as HTMLElement;
  return { onChange, stick, knob };
}

describe("Joystick", () => {
  it("starts with the knob centred", () => {
    const { knob } = setup();
    expect(knob.style.transform).toBe("translate(0px, 0px)");
  });

  it("reports a vector and moves the knob when pressed right of centre", () => {
    const { onChange, stick, knob } = setup();
    fireEvent.pointerDown(stick, { pointerId: 1, clientX: 100, clientY: 50 });
    expect(onChange).toHaveBeenCalledTimes(1);
    const v = onChange.mock.calls[0][0] as [number, number];
    expect(v[0]).toBeGreaterThan(0.5);
    expect(Math.hypot(v[0], v[1])).toBeLessThanOrEqual(1.0001);
    expect(knob.style.transform).not.toBe("translate(0px, 0px)");
  });

  it("clamps a drag far outside the stick to the unit circle", () => {
    const { onChange, stick } = setup();
    fireEvent.pointerDown(stick, { pointerId: 1, clientX: 50, clientY: 50 });
    fireEvent.pointerMove(stick, { pointerId: 1, clientX: 900, clientY: 900 });
    const v = onChange.mock.calls.at(-1)![0] as [number, number];
    expect(Math.hypot(v[0], v[1])).toBeLessThanOrEqual(1.0001);
  });

  it("follows moves from the active pointer only", () => {
    const { onChange, stick } = setup();
    fireEvent.pointerDown(stick, { pointerId: 1, clientX: 50, clientY: 50 });
    const n = onChange.mock.calls.length;
    fireEvent.pointerMove(stick, { pointerId: 2, clientX: 90, clientY: 50 });
    expect(onChange).toHaveBeenCalledTimes(n);
    fireEvent.pointerMove(stick, { pointerId: 1, clientX: 90, clientY: 50 });
    expect(onChange).toHaveBeenCalledTimes(n + 1);
  });

  it("ignores moves when nothing is pressed", () => {
    const { onChange, stick } = setup();
    fireEvent.pointerMove(stick, { pointerId: 1, clientX: 90, clientY: 50 });
    expect(onChange).not.toHaveBeenCalled();
  });

  it.each(["pointerUp", "pointerCancel"] as const)("%s recentres the knob", (name) => {
    const { onChange, stick, knob } = setup();
    fireEvent.pointerDown(stick, { pointerId: 1, clientX: 100, clientY: 50 });
    fireEvent[name](stick, { pointerId: 1 });
    expect(onChange).toHaveBeenLastCalledWith([0, 0]);
    expect(knob.style.transform).toBe("translate(0px, 0px)");
    const n = onChange.mock.calls.length;
    fireEvent.pointerMove(stick, { pointerId: 1, clientX: 90, clientY: 50 });
    expect(onChange).toHaveBeenCalledTimes(n);
  });
});
