import { describe, expect, it } from "vitest";
import type { PriceMarker } from "../../api/types";
import { PRICE_RANGES, formatPrice, markerLabel, rangeFrom } from "./priceModel";

const S = " ";
const TODAY = "2026-10-02";
const BUY: PriceMarker = {
  date: "2026-03-02", kind: "buy", price: "500.5", price_with_fx: "500.50", quantity: "2", amount_pln: "-4304.30",
};

describe("rangeFrom", () => {
  it("starts „Od zakupu” 14 days before the first purchase, a year back without one", () => {
    expect(rangeFrom("buy", "2026-03-02", TODAY)).toBe("2026-02-16");
    expect(rangeFrom("buy", null, TODAY)).toBe("2025-10-02");
  });

  it("counts the other ranges back from today, Maks from the beginning", () => {
    expect(rangeFrom("6m", "2026-03-02", TODAY)).toBe("2026-04-02");
    expect(rangeFrom("1y", "2026-03-02", TODAY)).toBe("2025-10-02");
    expect(rangeFrom("5y", "2026-03-02", TODAY)).toBe("2021-10-02");
    expect(rangeFrom("max", "2026-03-02", TODAY)).toBeNull();
  });

  it("lists the ranges in the order of the switch", () => {
    expect(PRICE_RANGES.map((range) => range.label)).toEqual(["Od zakupu", "6M", "1R", "5L", "Maks"]);
  });
});

describe("markerLabel", () => {
  it("names a purchase, a sale and a dividend", () => {
    expect(markerLabel(BUY, "EUR")).toBe(`Zakup 02.03.2026, 2 szt. po 500,50${S}€`);
    expect(markerLabel({ ...BUY, kind: "sell", quantity: "0.5", price: "609.1234" }, "USD"))
      .toBe(`Sprzedaż 02.03.2026, 0,5 szt. po 609,1234${S}$`);
    expect(markerLabel({ ...BUY, kind: "dividend", date: "2026-06-15", price: null, quantity: null, amount_pln: "40.00" }, "EUR"))
      .toBe(`Dywidenda 15.06.2026, +40,00${S}zł`);
  });
});

describe("formatPrice", () => {
  it("writes at least two places, up to four, with the currency symbol or code", () => {
    expect(formatPrice("270", "PLN")).toBe(`270,00${S}zł`);
    expect(formatPrice("1.23456", "CHF")).toBe(`1,2346${S}CHF`);
  });
});
