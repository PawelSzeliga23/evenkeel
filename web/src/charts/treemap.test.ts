import { describe, expect, it } from "vitest";
import { heatColor, squarify } from "./treemap";

const area = (r: { w: number; h: number }) => r.w * r.h;

describe("squarify", () => {
  it("gives each value an area in proportion, filling the map", () => {
    const rects = squarify([6, 6, 4, 3, 2, 2, 1], 600, 400);

    expect(rects.reduce((sum, r) => sum + area(r), 0)).toBeCloseTo(240_000, 3);
    expect(area(rects[0]!) / area(rects[6]!)).toBeCloseTo(6, 3);
    expect(area(rects[2]!)).toBeCloseTo(240_000 * 4 / 24, 3);
  });

  it("keeps the input order whatever the sizes", () => {
    const rects = squarify([1, 10], 100, 100);

    expect(area(rects[1]!)).toBeGreaterThan(area(rects[0]!));
  });

  it("keeps every rectangle inside the map", () => {
    for (const r of squarify([50, 20, 13, 8, 5, 3, 1], 340, 210)) {
      expect(r.x).toBeGreaterThanOrEqual(-1e-9);
      expect(r.y).toBeGreaterThanOrEqual(-1e-9);
      expect(r.x + r.w).toBeLessThanOrEqual(340 + 1e-9);
      expect(r.y + r.h).toBeLessThanOrEqual(210 + 1e-9);
    }
  });

  it("still gives a tiny holding a tile", () => {
    const rects = squarify([100_000, 0.01], 340, 210);

    expect(rects[1]!.w).toBeGreaterThan(0);
    expect(rects[1]!.h).toBeGreaterThan(0);
  });

  it("is empty for no values", () => {
    expect(squarify([], 100, 100)).toEqual([]);
  });
});

describe("heatColor", () => {
  it("is neutral at zero or without a percent", () => {
    expect(heatColor("0.00", "1d")).toBe("var(--slab)");
    expect(heatColor(null, "all")).toBe("var(--slab)");
  });

  it("is green for a gain and red for a loss, fully saturated at the period's limit", () => {
    expect(heatColor("3.00", "1d")).toBe(heatColor("9.00", "1d"));
    expect(heatColor("3.00", "1d")).toBe("color-mix(in srgb, var(--heat-gain) 70%, transparent)");
    expect(heatColor("-3.00", "1d")).toBe("color-mix(in srgb, var(--heat-loss) 70%, transparent)");
  });

  it("saturates later for longer periods", () => {
    expect(heatColor("3.00", "all")).not.toBe(heatColor("3.00", "1d"));
    expect(heatColor("50.00", "all")).toBe(heatColor("3.00", "1d"));
  });
});
