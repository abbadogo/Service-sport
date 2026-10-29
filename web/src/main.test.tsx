import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const render = vi.fn();
const createRoot = vi.fn(() => ({ render }));
vi.mock("react-dom/client", () => ({ createRoot }));
vi.mock("./App", () => ({ default: () => null }));
vi.mock("./styles.css", () => ({}));

beforeEach(() => {
  vi.resetModules();
  vi.clearAllMocks();
});
afterEach(() => {
  document.body.innerHTML = "";
});

describe("main", () => {
  it("mounts the app into #root", async () => {
    document.body.innerHTML = '<div id="root"></div>';
    await import("./main");
    expect(createRoot).toHaveBeenCalledWith(document.getElementById("root"));
    expect(render).toHaveBeenCalledTimes(1);
  });

  it("throws a clear error when #root is missing", async () => {
    await expect(import("./main")).rejects.toThrow("missing #root element");
    expect(render).not.toHaveBeenCalled();
  });
});
