import { describe, expect, it } from "vitest";
import { pwaOptions } from "./pwa.config";

describe("PWA", () => {
  const manifest = pwaOptions.manifest as Record<string, unknown> & { icons: { sizes: string; purpose?: string }[] };

  it("installs as a standalone dark app named Evenkeel", () => {
    expect(manifest).toMatchObject({
      name: "Evenkeel", short_name: "Evenkeel", lang: "pl", display: "standalone", start_url: "/",
      background_color: "#0E1116", theme_color: "#0E1116",
    });
  });

  it("ships the icons phones ask for, including a maskable one", () => {
    expect(manifest.icons.map((i) => i.sizes)).toEqual(expect.arrayContaining(["192x192", "512x512"]));
    expect(manifest.icons.some((i) => i.purpose === "maskable")).toBe(true);
  });

  it("never serves API answers from the cache", () => {
    const workbox = pwaOptions.workbox!;
    expect(workbox.runtimeCaching ?? []).toEqual([]);
    expect(workbox.navigateFallbackDenylist!.some((pattern) => pattern.test("/api/portfolio/summary"))).toBe(true);
  });
});
