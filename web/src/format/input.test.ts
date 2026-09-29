import { describe, expect, it } from "vitest";
import { isPositive, parseAmount } from ".";

describe("amount input", () => {
  it("reads Polish and plain amounts into API decimals", () => {
    expect(parseAmount("1 234,5")).toBe("1234.5");
    expect(parseAmount("1234.50")).toBe("1234.50");
    expect(parseAmount(" 10 000 ")).toBe("10000");
    expect(parseAmount("0,05")).toBe("0.05");
    expect(parseAmount("007")).toBe("7");
    expect(parseAmount("5,1234", 4)).toBe("5.1234");
  });

  it("refuses what is not an amount", () => {
    for (const text of ["", " ", "12,345", "-5", "1e3", "1,2,3", "abc", ",5", "5,"]) {
      expect(parseAmount(text)).toBeNull();
    }
    expect(parseAmount("5,12345", 4)).toBeNull();
  });

  it("tells a positive amount", () => {
    expect([isPositive("0"), isPositive("0.00"), isPositive("0.01"), isPositive("12")]).toEqual([false, false, true, true]);
  });
});
