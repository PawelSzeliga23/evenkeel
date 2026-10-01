import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, ANALYTICS, ANALYTICS_EMPTY } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";
import { formatPercent } from "../../format";
import { cellBackground, shownReturn } from "./model";

function routes(answer: (url: URL) => unknown) {
  return mockFetch([
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/analytics", respond: answer },
  ]);
}

const tile = (name: string) => screen.getByRole("group", { name });

describe("Analiza", () => {
  it("shows every measure with its caption", async () => {
    routes(() => ANALYTICS);
    renderApp("/analiza");

    expect(await screen.findByRole("heading", { name: "Analiza" })).toBeInTheDocument();
    expect(within(await screen.findByRole("group", { name: "Zysk" })).getByText("+804,20 zł")).toBeInTheDocument();
    expect(within(tile("TWR")).getByText("+8,0 %")).toBeInTheDocument();
    expect(within(tile("TWR")).getByText("za okres")).toBeInTheDocument();
    expect(within(tile("XIRR")).getByText("+6,4 %")).toBeInTheDocument();
    expect(within(tile("Maks. obsunięcie")).getByText("−8,2 %")).toBeInTheDocument();
    expect(within(tile("Maks. obsunięcie")).getByText("12.08.2026 → 22.08.2026 · odrobione 18.09.2026")).toBeInTheDocument();
    expect(within(tile("Obecne obsunięcie")).getByText("−1,3 %")).toBeInTheDocument();
    expect(within(tile("Zmienność")).getByText("14,8 %")).toBeInTheDocument();
    expect(within(tile("Zmienność")).getByText("rocznie · orientacyjnie")).toBeInTheDocument();
    expect(within(tile("Sharpe")).getByText("0,62")).toBeInTheDocument();
    expect(within(tile("Najlepszy dzień")).getByText("+2,9 %")).toBeInTheDocument();
    expect(within(tile("Najlepszy dzień")).getByText("+48,00 zł · 05.08.2026")).toBeInTheDocument();
    expect(within(tile("Najgorszy dzień")).getByText("−3,4 %")).toBeInTheDocument();
  });

  it("explains a measure behind its question mark", async () => {
    routes(() => ANALYTICS);
    const { user } = renderApp("/analiza");

    const help = await screen.findByRole("button", { name: "Co to jest: XIRR" });
    await user.hover(help);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Twój osobisty zwrot");
    expect(screen.getByRole("tooltip")).toHaveTextContent("Jak liczymy: stopa, przy której");
    await user.unhover(help);
    for (const name of ["Zysk", "TWR", "Maks. obsunięcie", "Obecne obsunięcie", "Zmienność", "Sharpe", "Najlepszy dzień", "Najgorszy dzień"]) {
      expect(screen.getByRole("button", { name: `Co to jest: ${name}` })).toBeInTheDocument();
    }
  });

  it("asks for the chosen period", async () => {
    const fetchMock = routes(() => ANALYTICS);
    const { user } = renderApp("/analiza");

    await screen.findByRole("group", { name: "Zysk" });
    expect(screen.getByRole("button", { name: "Wszystko" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Od pocz. roku" }));
    expect(fetchMock.mock.calls.map(([url]) => String(url)).some((u) => u.includes("period=ytd"))).toBe(true);
  });

  it("shows annual returns for a period of a year or more", async () => {
    routes(() => ({
      ...ANALYTICS,
      period: { ...ANALYTICS.period!, days: 365, annualized: true },
      twr: { period_pct: "9.70", annual_pct: "9.70" },
      short_sample: false,
    }));
    renderApp("/analiza");

    expect(within(await screen.findByRole("group", { name: "TWR" })).getByText("rocznie · za okres +9,7 %")).toBeInTheDocument();
    expect(within(tile("Zmienność")).getByText("rocznie")).toBeInTheDocument();
  });

  it("says when there is too little data for the risk measures", async () => {
    routes(() => ({ ...ANALYTICS, volatility_pct: null, sharpe: null }));
    renderApp("/analiza");

    expect(within(await screen.findByRole("group", { name: "Zmienność" })).getByText("za mało danych")).toBeInTheDocument();
    expect(within(tile("Sharpe")).getByText("za mało danych")).toBeInTheDocument();
  });

  it("shows a portfolio without a fall", async () => {
    routes(() => ({
      ...ANALYTICS,
      max_drawdown: { pct: "0.00", peak_date: "2026-09-26", trough_date: "2026-09-26", recovered_on: null },
      current_drawdown_pct: "0.00",
    }));
    renderApp("/analiza");

    expect(within(await screen.findByRole("group", { name: "Maks. obsunięcie" })).getByText("bez spadku od rekordu")).toBeInTheDocument();
  });

  it("shows an empty state without valuations", async () => {
    routes(() => ANALYTICS_EMPTY);
    renderApp("/analiza");

    expect(await screen.findByText("Nie ma jeszcze wyceny do pokazania.")).toBeInTheDocument();
  });

  it("shows an error with a retry", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/analytics", status: 500, respond: () => ({ code: "server_error", message: "x", details: {} }) }]);
    renderApp("/analiza");

    expect(await screen.findByRole("button", { name: "Spróbuj ponownie" })).toBeInTheDocument();
  });
  it("draws the drawdown over time", async () => {
    routes(() => ANALYTICS);
    renderApp("/analiza");

    expect(await screen.findByRole("img", { name: /^Obsunięcie w czasie, najgłębiej −8,2\s%$/ })).toBeInTheDocument();
  });

  it("lists monthly returns per year without a second copy", async () => {
    routes(() => ANALYTICS);
    renderApp("/analiza");

    const year = await screen.findByRole("group", { name: "Rok 2026" });
    expect(within(year).getByText("+5,1 %")).toBeInTheDocument();
    expect(within(year).getByRole("listitem", { name: "sie 2026" })).toHaveTextContent("−3,0 %");
    expect(within(year).getByRole("listitem", { name: "sty 2026" })).toHaveTextContent("–");
    expect(within(year).getAllByRole("listitem")).toHaveLength(12);
    expect(screen.getAllByRole("group", { name: /^Rok / })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Co to jest: Zwrot w miesiącach" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Co to jest: Obsunięcie w czasie" })).toBeInTheDocument();
  });

  it("marks the partial first month", async () => {
    routes(() => ({ ...ANALYTICS, monthly: [{ ...ANALYTICS.monthly[0]!, first_partial_month: 3 }] }));
    renderApp("/analiza");

    const march = await screen.findByRole("listitem", { name: "mar 2026, niepełny miesiąc" });
    expect(march).toHaveTextContent("+1,2 %");
  });
});

describe("analysis model", () => {
  it("picks the period or the annual return", () => {
    expect(shownReturn({ period_pct: "5.00", annual_pct: null }, false)).toEqual({ value: "5.00", caption: "za okres" });
    expect(shownReturn({ period_pct: "12.00", annual_pct: "10.00" }, true))
      .toEqual({ value: "10.00", caption: `rocznie · za okres ${formatPercent("12.00", { places: 1 })}` });
  });

  it("colours a month by its return, saturated at ±5 %", () => {
    expect(cellBackground(null)).toBe("transparent");
    expect(cellBackground("0.00")).toBe("transparent");
    expect(cellBackground("2.50")).toBe("rgba(93, 185, 138, 0.28)");
    expect(cellBackground("-9.00")).toBe("rgba(224, 103, 110, 0.55)");
  });
});
