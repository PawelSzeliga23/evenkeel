/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The API runs in docker on :8000 (e2e: its own instance, API_TARGET=http://localhost:8001). Proxying /api keeps the
// browser on one origin, so the httpOnly refresh cookie works without CORS.
const apiTarget = process.env.API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: apiTarget } } },
  preview: { proxy: { "/api": { target: apiTarget } } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "*.test.ts"],
    css: { include: [/.+/], modules: { classNameStrategy: "non-scoped" } },
    restoreMocks: true,
  },
});
