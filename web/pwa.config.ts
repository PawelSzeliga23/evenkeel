import type { VitePWAOptions } from "vite-plugin-pwa";

/** The service worker keeps only the app's own files: money always comes fresh from the API. */
export const pwaOptions: Partial<VitePWAOptions> = {
  registerType: "autoUpdate",
  injectRegister: "auto",
  includeAssets: ["favicon.ico", "apple-touch-icon-180x180.png", "icon.svg"],
  manifest: {
    name: "Evenkeel",
    short_name: "Evenkeel",
    description: "Cały portfel inwestycyjny w jednym miejscu.",
    lang: "pl",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#0E1116",
    theme_color: "#0E1116",
    icons: [
      { src: "pwa-64x64.png", sizes: "64x64", type: "image/png" },
      { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
      { src: "pwa-512x512.png", sizes: "512x512", type: "image/png" },
      { src: "maskable-icon-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  },
  workbox: {
    globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2}"],
    navigateFallback: "/index.html",
    navigateFallbackDenylist: [/^\/api\//],
    runtimeCaching: [],
  },
  devOptions: { enabled: false },
};
