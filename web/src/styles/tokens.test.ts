import { describe, expect, it } from "vitest";
import tokens from "./tokens.css?raw";

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
  ])("%s is %s", (name, value) => {
    expect(tokens).toMatch(new RegExp(`${name}:\\s*${value};`, "i"));
  });

  it("uses Instrument Sans with a system fallback", () => {
    expect(tokens).toMatch(/--font:\s*"Instrument Sans Variable",[^;]*system-ui/);
  });
});
