import { describe, expect, it } from "vitest";
import { HOLDINGS } from "../../test/fixtures";
import { shown } from "./model";

describe("shown", () => {
  it("on a losing period gives each holding its part of the loss, a gainer offsetting it", () => {
    const [a, b] = HOLDINGS.items;
    const rows = shown([{ ...a!, gain_pln: "100.00" }, { ...b!, gain_pln: "-300.00" }], false);

    expect(rows.map((row) => row.contribution)).toEqual(["−50,0\u00a0% straty", "150,0\u00a0% straty"]);
  });
});
