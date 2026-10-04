import { describe, expect, it } from "vitest";
import charts from "./chart-colors.css?raw";
import theme from "./theme.css?raw";

/** The variables declared in the dark (:root) and light (:root[data-theme="light"]) blocks of a colour file. */
function blocks(css: string): { dark: Set<string>; light: Set<string> } {
  const light = css.indexOf(':root[data-theme="light"]');
  const names = (text: string) => new Set([...text.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]!));
  return { dark: names(css.slice(0, light)), light: names(css.slice(light)) };
}

describe("design tokens", () => {
  it.each([
    ["--night", "#0E1116"],
    ["--slab", "#161A21"],
    ["--rule", "#242A33"],
    ["--ink", "#E7E9EC"],
    ["--dim", "#8B94A1"],
    ["--amber", "#F0A43A"],
    ["--gain", "#5DB98A"],
    ["--loss", "#E0676E"],
  ])("dark %s is %s", (name, value) => {
    expect(theme).toMatch(new RegExp(`${name}:\\s*${value};`, "i"));
  });

  it("uses Instrument Sans with a system fallback", () => {
    expect(theme).toMatch(/--font:\s*"Instrument Sans Variable",[^;]*system-ui/);
  });

  it.each([["theme.css", theme], ["chart-colors.css", charts]])("%s sets every light colour in dark too", (_, css) => {
    const { dark, light } = blocks(css);
    expect(light.size).toBeGreaterThan(0);
    expect([...light].filter((name) => !dark.has(name))).toEqual([]);
  });

  it("chart-colors.css sets every dark colour in light too", () => {
    const { dark, light } = blocks(charts);
    expect([...dark].filter((name) => !light.has(name))).toEqual([]);
  });

  it("theme.css sets every dark colour in light, except the shared mark, font and sizes", () => {
    const { dark, light } = blocks(theme);
    const shared = (name: string) => /^--(brand-|font|r-|nav-h)/.test(name);
    expect([...dark].filter((name) => !shared(name) && !light.has(name))).toEqual([]);
  });
});
