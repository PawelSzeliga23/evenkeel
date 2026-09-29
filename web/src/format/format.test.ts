import { describe, expect, it } from "vitest";
import {
  addMonths, formatDate, formatDateTime, formatDayLong, formatDays, formatDecimal, formatMoney, formatPercent,
  fromCents, moneyParts, monthShort, signOf, sumMoney, toCents, todayIso,
} from ".";

const S = " ";
const M = "−";

describe("decimal", () => {
  it("rounds half up to the grosz on the text, never through a float", () => {
    expect(toCents("1001.30")).toBe(100130n);
    expect(toCents("0.004")).toBe(0n);
    expect(toCents("0.005")).toBe(1n);
    expect(toCents("-1234567.891")).toBe(-123456789n);
    expect(toCents("10000.0000")).toBe(1000000n);
    expect(toCents("0.1")).toBe(10n);
    expect(toCents("99.995")).toBe(10000n);
    expect(toCents("7")).toBe(700n);
  });

  it("sums money exactly", () => {
    expect(sumMoney(["0.10", "0.20", "1001.30"])).toBe("1001.60");
    expect(sumMoney(["-5.00", "2.50"])).toBe("-2.50");
    expect(sumMoney([])).toBe("0.00");
    expect(fromCents(-5n)).toBe("-0.05");
  });

  it("tells the sign", () => {
    expect([signOf("12.30"), signOf("-0.01"), signOf("-0.00"), signOf("0.004"), signOf(null)]).toEqual([1, -1, 0, 0, 0]);
  });
});

describe("money", () => {
  it("writes Polish amounts with a space in every thousand", () => {
    expect(formatMoney("184302.17")).toBe(`184${S}302,17${S}zł`);
    expect(formatMoney("1204.5")).toBe(`1${S}204,50${S}zł`);
    expect(formatMoney("10000.0000")).toBe(`10${S}000,00${S}zł`);
    expect(formatMoney("-1234567.891")).toBe(`${M}1${S}234${S}567,89${S}zł`);
    expect(formatMoney("0.5", { currency: "EUR" })).toBe(`0,50${S}EUR`);
    expect(formatMoney("12", { currency: null })).toBe("12,00");
  });

  it("shows the sign of a change and none for zero", () => {
    expect(formatMoney("1204.50", { sign: true })).toBe(`+1${S}204,50${S}zł`);
    expect(formatMoney("-151.2", { sign: true })).toBe(`${M}151,20${S}zł`);
    expect(formatMoney("-0.00", { sign: true })).toBe(`0,00${S}zł`);
    expect(formatMoney("-0.004")).toBe(`0,00${S}zł`);
  });

  it("splits a big amount into its parts", () => {
    expect(moneyParts("184302.17")).toEqual({ sign: "", whole: `184${S}302`, grosze: "17" });
    expect(moneyParts("-3.1", { sign: true })).toEqual({ sign: M, whole: "3", grosze: "10" });
    expect(moneyParts("3.1", { sign: true })).toEqual({ sign: "+", whole: "3", grosze: "10" });
  });

  it("writes quantities without trailing zeros", () => {
    expect(formatDecimal("42.00000000", 8)).toBe("42");
    expect(formatDecimal("0.12345678", 4)).toBe("0,1235");
    expect(formatDecimal("1234.5", 8)).toBe(`1${S}234,5`);
  });

  it("writes percents with a space before the sign", () => {
    expect(formatPercent("0.66")).toBe(`+0,66${S}%`);
    expect(formatPercent("-2.071")).toBe(`${M}2,07${S}%`);
    expect(formatPercent("14.2", { places: 1 })).toBe(`+14,2${S}%`);
    expect(formatPercent("33.4", { sign: false, places: 1 })).toBe(`33,4${S}%`);
    expect(formatPercent(null)).toBe("—");
  });
});

describe("dates", () => {
  it("formats days without time-zone shifts", () => {
    expect(formatDate("2026-09-26")).toBe("26.09.2026");
    expect(formatDayLong("2026-09-26")).toBe("sob., 26 września");
    expect(formatDayLong("2026-03-01")).toBe("niedz., 1 marca");
    expect(monthShort("2026-10-01")).toBe("paź");
    expect(formatDateTime("2026-03-02T09:30:00")).toBe("02.03.2026, 09:30");
    expect(formatDateTime("2026-03-02T09:30:00+00:00")).toBe("02.03.2026, 09:30");
  });

  it("counts days in Polish", () => {
    expect([formatDays(1), formatDays(2), formatDays(412)]).toEqual(["1 dzień", "2 dni", "412 dni"]);
  });

  it("moves by months and clamps the day", () => {
    expect(addMonths("2026-09-26", -1)).toBe("2026-08-26");
    expect(addMonths("2026-03-31", -1)).toBe("2026-02-28");
    expect(addMonths("2026-01-15", -12)).toBe("2025-01-15");
    expect(todayIso(new Date(2026, 8, 28, 23, 59))).toBe("2026-09-28");
  });
});
