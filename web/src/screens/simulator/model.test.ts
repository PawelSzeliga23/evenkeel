import { describe, expect, it } from "vitest";
import type { Scenario } from "../../api/types";
import { scenarioResult } from "../../test/fixtures";
import {
  EDO, NEW_DRAFT, defaultShown, difference, draftOf, newRecurring, newReplace, newShare, toBody, toggleShown,
  type Draft,
} from "./model";

const named = (draft: Partial<Draft>): Draft => ({ ...NEW_DRAFT, name: "Test", ...draft });

describe("toBody", () => {
  it("builds the API body of a deposits scenario", () => {
    const draft = named({ base: "deposits", allocation: [{ target: "20", pct: "60" }, { target: EDO, pct: "40" }] });

    expect(toBody(draft)).toEqual({
      errors: {},
      body: {
        name: "Test", base: "deposits", steps: [],
        allocation: [
          { target: { instrument_id: 20, bond: null }, share_pct: "60" },
          { target: { instrument_id: null, bond: "EDO" }, share_pct: "40" },
        ],
      },
    });
  });

  it("builds replace and top-up blocks", () => {
    const draft = named({ steps: [
      { kind: "replace", from: "10", to: "20" },
      { kind: "recurring", amount: "1 000,50", day: "10", start: "2024-01", end: "", target: EDO, ike: true },
    ] });

    expect(toBody(draft).body?.steps).toEqual([
      { kind: "replace", from_instrument_id: 10, to_instrument_id: 20 },
      { kind: "recurring", amount_pln: "1000.50", day_of_month: 10, start: "2024-01", end: null,
        target: { instrument_id: null, bond: "EDO" }, ike: true },
    ]);
  });

  it("says what is wrong, field by field", () => {
    const draft: Draft = {
      name: "  ", base: "deposits", allocation: [{ target: EDO, pct: "90" }],
      steps: [{ kind: "recurring", amount: "abc", day: "10", start: "2015-12", end: "", target: EDO, ike: false }],
    };

    expect(toBody(draft)).toEqual({
      body: null,
      errors: {
        name: "Podaj nazwę scenariusza.",
        allocation: "Udziały muszą dawać razem 100 %.",
        "steps.0.amount": "Podaj kwotę, np. 1 250,50.",
        "steps.0.start": "Dopłaty mogą zaczynać się najwcześniej w 01.2016.",
      },
    });
  });

  it("refuses a replace block at deposits", () => {
    const draft = named({ base: "deposits", allocation: [newShare()], steps: [{ kind: "replace", from: "10", to: "20" }] });

    expect(toBody(draft).errors).toEqual({ "steps.0.from": "Podmiana działa tylko na punkcie wyjścia „Mój portfel”." });
  });

  it("refuses an unfinished or doubled replace and an end before the start", () => {
    const draft = named({ steps: [
      { kind: "replace", from: "10", to: "" },
      { kind: "replace", from: "11", to: "11" },
      { kind: "recurring", amount: "100", day: "1", start: "2024-05", end: "2024-01", target: EDO, ike: false },
    ] });

    expect(toBody(draft).errors).toEqual({
      "steps.0.to": "Wybierz instrument, który kupujesz w zamian.",
      "steps.1.to": "Wybierz inny instrument niż podmieniany.",
      "steps.2.end": "Koniec nie może być przed początkiem.",
    });
  });

  it("refuses the same instrument replaced twice", () => {
    const draft = named({ steps: [{ kind: "replace", from: "10", to: "20" }, { kind: "replace", from: "10", to: "30" }] });

    expect(toBody(draft).errors).toEqual({ "steps.1.from": "Ten instrument jest już podmieniony." });
  });
});

describe("draftOf", () => {
  it("turns a saved scenario back into the editor's draft", () => {
    const saved: Scenario = {
      id: 5, name: "Mix", base: "deposits", created_at: "", updated_at: "",
      allocation: [{ target: { instrument_id: 20, bond: null }, share_pct: "62.5" }, { target: { instrument_id: null, bond: "EDO" }, share_pct: "37.5" }],
      steps: [{ kind: "recurring", amount_pln: "1000", day_of_month: 3, start: "2024-01", end: null,
                target: { instrument_id: null, bond: "EDO" }, ike: false }],
    };

    expect(draftOf(saved)).toEqual({
      name: "Mix", base: "deposits",
      allocation: [{ target: "20", pct: "62,5" }, { target: EDO, pct: "37,5" }],
      steps: [{ kind: "recurring", amount: "1000", day: "3", start: "2024-01", end: "", target: EDO, ike: false }],
    });
    expect(toBody(draftOf(saved)).body?.allocation[0]?.share_pct).toBe("62.5");
  });

  it("has sensible new blocks", () => {
    expect(newShare()).toEqual({ target: EDO, pct: "100" });
    expect(newReplace()).toEqual({ kind: "replace", from: "", to: "" });
    expect(newRecurring("2025-10")).toEqual(
      { kind: "recurring", amount: "1000", day: "10", start: "2025-10", end: "", target: EDO, ike: false });
  });
});

describe("difference", () => {
  it("is the value and XIRR against the portfolio", () => {
    expect(difference(scenarioResult("12044.20", "9.50"))).toBe("+1 240,00 zł · +3,1 pkt XIRR");
    expect(difference(scenarioResult("9804.20", "5.00"))).toBe("−1 000,00 zł · −1,4 pkt XIRR");
  });

  it("is the value alone when an XIRR is missing or counted over a different span", () => {
    const result = scenarioResult("12044.20", "9.50");
    expect(difference({ ...result, scenario: { ...result.scenario!, xirr: { period_pct: null, annual_pct: null } } }))
      .toBe("+1 240,00 zł");
    const yearly = { ...result.scenario!, period: { ...result.scenario!.period, annualized: true },
      xirr: { period_pct: "20.00", annual_pct: "9.00" } };
    expect(difference({ ...result, scenario: yearly })).toBe("+1 240,00 zł");
    expect(difference({ ...result, scenario: null })).toBeNull();
  });
});

describe("shown scenarios", () => {
  it("shows the first three by default", () => {
    expect(defaultShown([4, 3, 2, 1])).toEqual([{ id: 4, slot: 0 }, { id: 3, slot: 1 }, { id: 2, slot: 2 }]);
  });

  it("toggleShown keeps the slots of the others", () => {
    const shown = defaultShown([4, 3, 2, 1]);
    const hidden = toggleShown(shown, 4);
    expect(hidden).toEqual([{ id: 3, slot: 1 }, { id: 2, slot: 2 }]);
    expect(toggleShown(hidden, 1)).toEqual([{ id: 3, slot: 1 }, { id: 2, slot: 2 }, { id: 1, slot: 0 }]);
    expect(toggleShown(shown, 1)).toBe(shown); // a fourth waits for a free slot
  });
});
