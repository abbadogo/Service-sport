import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReplayEvent } from "../types";
import { EventLog } from "./EventLog";

afterEach(cleanup);

const ev = (t: number, kind: string, text: string) =>
  ({ t, kind, text }) as unknown as ReplayEvent;

describe("EventLog", () => {
  it("shows the empty message when nothing has happened yet", () => {
    render(<EventLog events={[ev(10, "hit", "late")]} time={5} onJump={() => {}} />);
    expect(screen.getByText("Nothing yet.")).toBeTruthy();
  });

  it("hides serve events and future events, newest first", () => {
    const events = [
      ev(1, "serve", "serve text"),
      ev(2, "hit", "first"),
      ev(3, "point", "second"),
      ev(99, "hit", "future"),
    ];
    const { container } = render(<EventLog events={events} time={10} onJump={() => {}} />);
    const items = Array.from(container.querySelectorAll("li")).map((l) => l.textContent);
    expect(items).toHaveLength(2);
    expect(items[0]).toContain("second");
    expect(items[1]).toContain("first");
    expect(container.textContent).not.toContain("serve text");
    expect(container.textContent).not.toContain("future");
    expect(container.querySelector("li")?.className).toBe("point");
  });

  it("jumps to 4 seconds before the event, never below 0", () => {
    const onJump = vi.fn();
    render(
      <EventLog
        events={[ev(2, "hit", "early"), ev(9, "point", "later")]}
        time={20}
        onJump={onJump}
      />,
    );
    fireEvent.click(screen.getByText("later"));
    expect(onJump).toHaveBeenLastCalledWith(5);
    fireEvent.click(screen.getByText("early"));
    expect(onJump).toHaveBeenLastCalledWith(0);
  });
});
