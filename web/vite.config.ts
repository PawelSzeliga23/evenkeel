/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import pkg from "./package.json" with { type: "json" };
import { pwaOptions } from "./pwa.config.ts";

// The API runs in docker on :8000 (e2e: its own instance, API_TARGET=http://localhost:8001). Proxying /api keeps the
// browser on one origin, so the httpOnly refresh cookie works without CORS.
const apiTarget = process.env.API_TARGET ?? "http://localhost:8000";

export default defineConfig(({ mode }) => ({
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  plugins: [react(), ...(mode === "test" ? [] : [VitePWA(pwaOptions)])],
  server: { port: 5173, proxy: { "/api": { target: apiTarget } } },
  // the iPhone PWA test goes through a quick Cloudflare tunnel (https://*.trycloudflare.com) to `vite preview`
  preview: { allowedHosts: [".trycloudflare.com"], proxy: { "/api": { target: apiTarget } } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "*.test.ts"],
    // include: [/.+/] makes Vitest process CSS, which the ?raw CSS imports and CSS Modules need.
    css: { include: [/.+/], modules: { classNameStrategy: "non-scoped" } },
    restoreMocks: true,
  },
}));
