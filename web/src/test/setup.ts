import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Vitest runs without globals here, so Testing Library cannot register its own
// cleanup. Without this, rendered components pile up between tests (and duplicate
// element ids make queries return elements from an earlier test).
afterEach(() => {
  cleanup();
});
