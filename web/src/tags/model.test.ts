import { describe, expect, it } from "vitest";
import { TAG_PALETTE, tagColor } from "./model";

describe("tagColor", () => {
  it("paints a palette colour with its slot of the current theme", () => {
    expect(TAG_PALETTE.map(tagColor)).toEqual(TAG_PALETTE.map((_, i) => `var(--tag-${i + 1})`));
  });

  it("ignores the case of the stored value", () => {
    expect(tagColor(TAG_PALETTE[1].toLowerCase())).toBe("var(--tag-2)");
  });

  it("passes a colour from outside the palette through", () => {
    const other = ["#", "123456"].join("");
    expect(tagColor(other)).toBe(other);
  });
});
