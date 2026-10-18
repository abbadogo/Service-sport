import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the browser talks to Vite, which forwards /api to the Python server.
export default defineConfig({
  plugins: [react()],
  server: { host: true, proxy: { "/api": "http://127.0.0.1:8000" } },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"] },
});
