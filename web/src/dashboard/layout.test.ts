import { describe, expect, it } from "vitest";
import { DEFAULT_LAYOUT, KINDS, MAX_TILES, addTile, moveTile, normalize, removeTile, sameLayout, updateTile } from "./layout";

describe("dashboard layout", () => {
  it("is today's Pulpit by default", () => {
    expect(DEFAULT_LAYOUT.tiles.map((t) => `${t.kind}:${t.size}`)).toEqual(
      ["summary:L", "value_chart:L", "allocation:L", "analysis:M", "limits:M", "movers:L"]);
    expect(DEFAULT_LAYOUT.tiles[0]!.settings).toEqual({ fields: ["total_gain", "twr_total", "invested", "income"] });
  });

  it("falls back to the default layout and drops broken tiles", () => {
    expect(normalize(null)).toEqual(DEFAULT_LAYOUT);
    expect(normalize({ version: 7, tiles: [] })).toEqual(DEFAULT_LAYOUT);
    const stored = { version: 1, tiles: [
      { id: "a", kind: "weather", size: "M", settings: {} },
      { id: "b", kind: "metric", size: "S", settings: { metric: "sharpe" } },
      { id: "c", kind: "metric", size: "L", settings: { metric: "sharpe" } },
      { id: "d", kind: "metric", size: "S", settings: { metric: "luck" } },
      { id: "b", kind: "limits", size: "M", settings: {} },
    ] };
    expect(normalize(stored).tiles.map((t) => t.id)).toEqual(["b"]);
  });

  it("adds at the start with the kind's defaults, moves, updates and removes", () => {
    let layout = addTile(DEFAULT_LAYOUT, "metric", "new1");
    expect(layout.tiles[0]).toEqual({ id: "new1", kind: "metric", size: "S", settings: { metric: "xirr" } });
    layout = moveTile(layout, "new1", 2);
    expect(layout.tiles.map((t) => t.id).indexOf("new1")).toBe(2);
    layout = updateTile(layout, "new1", { settings: { metric: "sharpe" } });
    expect(layout.tiles[2]!.settings).toEqual({ metric: "sharpe" });
    expect(removeTile(layout, "new1")).toEqual(DEFAULT_LAYOUT);
  });

  it("keeps a move inside the list and stops adding at the limit", () => {
    expect(moveTile(DEFAULT_LAYOUT, DEFAULT_LAYOUT.tiles[0]!.id, 99).tiles.at(-1)!.kind).toBe("summary");
    let full = DEFAULT_LAYOUT;
    for (let i = full.tiles.length; i < MAX_TILES; i++) full = addTile(full, "limits", `x${i}`);
    expect(addTile(full, "limits", "over")).toBe(full);
  });

  it("knows the sizes of each kind and compares layouts", () => {
    expect(KINDS.metric.sizes).toEqual(["S"]);
    expect(KINDS.allocation.sizes).toEqual(["S", "L"]);
    expect(sameLayout(normalize(JSON.parse(JSON.stringify(DEFAULT_LAYOUT))), DEFAULT_LAYOUT)).toBe(true);
    expect(sameLayout(addTile(DEFAULT_LAYOUT, "limits", "z"), DEFAULT_LAYOUT)).toBe(false);
  });
});
