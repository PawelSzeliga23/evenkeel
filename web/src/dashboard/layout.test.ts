import { describe, expect, it } from "vitest";
import {
  DEFAULT_LAYOUT, KINDS, MAX_TILES, addTile, dimensionOf, heightOf, moveTile, normalize, removeTile, sameLayout,
  updateTile, type Tile,
} from "./layout";
import type { MetricKey } from "./metrics";

const metrics = (n: number) => (["xirr", "twr", "sharpe", "volatility", "max_drawdown", "best_day", "worst_day", "fees"] as MetricKey[]).slice(0, n);
const summary = (variant: string, n: number): Tile => ({ id: "s", kind: "summary", variant, settings: { fields: metrics(n) } });
const analysis = (variant: string, n: number): Tile => ({ id: "a", kind: "analysis", variant, settings: { metrics: metrics(n), period: "all" } });

describe("dashboard layout", () => {
  it("is today's Pulpit by default, without gaps on a computer", () => {
    expect(DEFAULT_LAYOUT.tiles.map((t) => `${t.kind}:${t.variant}:${heightOf(t)}`)).toEqual(
      ["summary:L:3", "value_chart:L6:6", "allocation:M4:4", "analysis:M:2", "limits:M2:2", "movers:L:3"]);
    expect(DEFAULT_LAYOUT.tiles[0]!.settings).toEqual({ fields: ["total_gain", "twr_total", "invested", "income"] });
  });

  it("falls back to the default layout and drops broken tiles", () => {
    expect(normalize(null)).toEqual(DEFAULT_LAYOUT);
    expect(normalize({ version: 7, tiles: [] })).toEqual(DEFAULT_LAYOUT);
    const stored = { version: 1, tiles: [
      { id: "a", kind: "weather", variant: "M3", settings: {} },
      { id: "b", kind: "metric", variant: "S1", settings: { metric: "sharpe" } },
      { id: "c", kind: "metric", variant: "M4", settings: { metric: "sharpe" } },
      { id: "d", kind: "metric", variant: "S2", settings: { metric: "luck" } },
      { id: "b", kind: "limits", variant: "M2", settings: {} },
      { id: "e", kind: "toString", variant: "S2", settings: {} },
      { id: "f", kind: "limits", variant: "M2", size: "M", settings: {} },
    ] };
    expect(normalize(stored).tiles.map((t) => t.id)).toEqual(["b"]);
  });

  it("reads a layout of plan 9 (sizes) as the nearest variants", () => {
    const stored = { version: 1, tiles: [
      { id: "s", kind: "summary", size: "L", settings: { fields: ["xirr"] } },
      { id: "m", kind: "metric", size: "S", settings: { metric: "xirr" } },
      { id: "v", kind: "value_chart", size: "M", settings: { range: "1R" } },
      { id: "a", kind: "analysis", size: "L", settings: { metrics: ["xirr"], period: "all" } },
      { id: "h", kind: "holdings", size: "M", settings: {} },
      { id: "x", kind: "metric", size: "L", settings: { metric: "xirr" } },
    ] };
    expect(normalize(stored).tiles).toEqual([
      { id: "s", kind: "summary", variant: "L", settings: { fields: ["xirr"] } },
      { id: "m", kind: "metric", variant: "S2", settings: { metric: "xirr" } },
      { id: "v", kind: "value_chart", variant: "M4", settings: { range: "1R" } },
      { id: "a", kind: "analysis", variant: "Lc", settings: { metrics: ["xirr"], period: "all" } },
      { id: "h", kind: "holdings", variant: "M3", settings: {} },
    ]);
  });

  it("grows a tile with the number of the chosen fields", () => {
    expect([2, 4, 6].map((n) => heightOf(analysis("M", n)))).toEqual([2, 3, 4]);
    expect([4, 6].map((n) => heightOf(analysis("L", n)))).toEqual([2, 3]);
    expect([4, 6].map((n) => heightOf(analysis("Lc", n)))).toEqual([5, 6]);
    expect([1, 3, 6].map((n) => heightOf(analysis("S", n)))).toEqual([2, 4, 4]);
    expect([4, 6, 8].map((n) => heightOf(summary("M", n)))).toEqual([4, 5, 6]);
    expect([4, 8].map((n) => heightOf(summary("L", n)))).toEqual([3, 4]);
    expect(heightOf(summary("S2", 8))).toBe(2);
    const movers = (variant: string, count: 3 | 5 | 10): Tile => ({ id: "m", kind: "movers", variant, settings: { count } });
    expect([3, 5, 10].map((n) => heightOf(movers("M", n as 3 | 5 | 10)))).toEqual([3, 4, 6]);
    expect([5, 10].map((n) => heightOf(movers("L", n as 3 | 5 | 10)))).toEqual([3, 4]);
    const ops: Tile = { id: "o", kind: "operations", variant: "M", settings: { count: 5 } };
    expect(heightOf(ops)).toBe(4);
    const extremes = (variant: string): Tile => ({ id: "e", kind: "extremes", variant, settings: { count: 3, period: "all" } });
    expect([heightOf(extremes("M")), heightOf(extremes("L")), heightOf(extremes("S2"))]).toEqual([4, 3, 2]);
    expect(dimensionOf(analysis("Lc", 4))).toBe("L + wykres · 5U");
    expect(dimensionOf(summary("M", 4))).toBe("M · 4U");
  });

  it("adds at the start with the kind's defaults, moves, updates and removes", () => {
    let layout = addTile(DEFAULT_LAYOUT, "metric", undefined, "new1");
    expect(layout.tiles[0]).toEqual({ id: "new1", kind: "metric", variant: "S2", settings: { metric: "xirr" } });
    layout = moveTile(layout, "new1", 2);
    expect(layout.tiles.map((t) => t.id).indexOf("new1")).toBe(2);
    layout = updateTile(layout, "new1", { settings: { metric: "sharpe" }, variant: "S1" });
    expect(layout.tiles[2]).toMatchObject({ variant: "S1", settings: { metric: "sharpe" } });
    expect(removeTile(layout, "new1")).toEqual(DEFAULT_LAYOUT);
    expect(addTile(DEFAULT_LAYOUT, "allocation", "S2", "x").tiles[0]!.variant).toBe("S2");
    expect(addTile(DEFAULT_LAYOUT, "allocation", "L9", "x").tiles[0]!.variant).toBe("L4");
    expect(addTile(DEFAULT_LAYOUT, "extremes", undefined, "x").tiles[0]).toMatchObject({ settings: { count: 3, period: "all" } });
  });

  it("keeps a move inside the list and stops adding at the limit", () => {
    expect(moveTile(DEFAULT_LAYOUT, DEFAULT_LAYOUT.tiles[0]!.id, 99).tiles.at(-1)!.kind).toBe("summary");
    let full = DEFAULT_LAYOUT;
    for (let i = full.tiles.length; i < MAX_TILES; i++) full = addTile(full, "limits", undefined, `x${i}`);
    expect(addTile(full, "limits", undefined, "over")).toBe(full);
  });

  it("knows the variants of each kind and compares layouts", () => {
    expect(KINDS.metric.variants).toEqual(["S1", "S2"]);
    expect(KINDS.allocation.variants).toEqual(["S2", "M4", "L4"]);
    expect(sameLayout(normalize(JSON.parse(JSON.stringify(DEFAULT_LAYOUT))), DEFAULT_LAYOUT)).toBe(true);
    expect(sameLayout(addTile(DEFAULT_LAYOUT, "limits", undefined, "z"), DEFAULT_LAYOUT)).toBe(false);
  });
});
