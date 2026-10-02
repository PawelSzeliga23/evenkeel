import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, ANALYTICS, scenario, scenarioResult } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";

const FOUR = [scenario(1, "A"), scenario(2, "B"), scenario(3, "C"), scenario(4, "D")];
const VALUES: Record<string, string> = { 1: "12044.20", 2: "11000.00", 3: "10000.00", 4: "9000.00" };

function routes(scenarios = FOUR) {
  return mockFetch([
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/analytics", respond: () => ANALYTICS },
    { path: "/api/scenarios", respond: () => scenarios },
    { path: /^\/api\/scenarios\/\d+\/result$/, respond: (url) => scenarioResult(VALUES[url.pathname.split("/")[3]!]!, "9.50") },
  ]);
}

const legend = () => screen.getByRole("group", { name: "Linie na wykresie" });
const stroke = (key: string) => document.querySelector(`path[data-line="${key}"]`)?.getAttribute("stroke");

describe("Symulator", () => {
  it("lists the scenarios with their difference and draws the first three", async () => {
    routes();
    const { user } = renderApp("/analiza/symulator");

    expect(await screen.findByRole("heading", { name: "Symulator" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /^AMój portfel.*\+1\s240,00\szł · \+3,1\spkt XIRR/ })).toHaveAttribute(
      "href", "/analiza/symulator/1");
    for (const name of ["Mój portfel", "A", "B", "C"]) {
      expect(within(legend()).getByRole("button", { name })).toHaveAttribute("aria-pressed", "true");
    }
    const fourth = within(legend()).getByRole("button", { name: "D" });
    expect(fourth).toHaveAttribute("aria-disabled", "true");
    expect(fourth).toHaveAccessibleDescription(/mieszczą się 3 scenariusze/);
    await user.click(fourth);
    expect(fourth).toHaveAttribute("aria-pressed", "false");
    expect(await screen.findByRole("img", { name: "Porównanie wartości: Mój portfel, A, B, C" })).toBeInTheDocument();
  });

  it("a newly shown scenario takes the freed colour", async () => {
    routes();
    const { user } = renderApp("/analiza/symulator");
    await screen.findByRole("img", { name: "Porównanie wartości: Mój portfel, A, B, C" });

    expect(stroke("1")).toBe("#3987e5");
    await user.click(within(legend()).getByRole("button", { name: "A" }));
    await user.click(within(legend()).getByRole("button", { name: "D" }));

    expect(stroke("4")).toBe("#3987e5");
    expect(stroke("2")).toBe("#d55181");
    expect(stroke("1")).toBeUndefined();
  });

  it("compares the measures line by line", async () => {
    routes();
    renderApp("/analiza/symulator");

    const ours = await screen.findByRole("group", { name: "Mój portfel" });
    expect(within(ours).getByText("10 804,20 zł")).toBeInTheDocument();
    const theirs = await screen.findByRole("group", { name: "A" });
    expect(within(theirs).getByText("12 044,20 zł")).toBeInTheDocument();
    expect(within(theirs).getByText("+9,5 %")).toBeInTheDocument();
    expect(within(ours).getByRole("button", { name: "Co to jest: XIRR" })).toBeInTheDocument();
    expect(within(ours).getByText("Wpłacono w okresie")).toBeInTheDocument();
  });

  it("asks for the chosen period", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator");
    await screen.findByRole("img", { name: /Porównanie wartości/ });

    await user.click(screen.getByRole("button", { name: "1R" }));
    expect(fetchMock.mock.calls.map(([url]) => String(url)).some((u) => u.includes("/result") && u.includes("period=1y")))
      .toBe(true);
  });

  it("invites to the first scenario", async () => {
    routes([]);
    renderApp("/analiza/symulator");

    expect(await screen.findByText("Nie masz jeszcze scenariuszy.")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Nowy scenariusz" })[0]).toHaveAttribute("href", "/analiza/symulator/nowy");
  });

  it("shows the three latest scenarios on Analiza", async () => {
    routes();
    renderApp("/analiza");

    const card = await screen.findByRole("region", { name: "Symulator" });
    expect(await within(card).findAllByRole("link", { name: /^[ABC]Mój portfel/ })).toHaveLength(3);
    expect(within(card).queryByRole("link", { name: /^DMój portfel/ })).not.toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Wszystkie scenariusze" })).toHaveAttribute("href", "/analiza/symulator");
    expect(within(card).getByText("Różnica względem portfela za cały okres.")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Nowy scenariusz" })).toHaveAttribute("href", "/analiza/symulator/nowy");
  });
});

describe("Symulator chart lines", () => {
  it("keeps the portfolio on the chart when every scenario is hidden", async () => {
    routes();
    const { user } = renderApp("/analiza/symulator");
    await screen.findByRole("img", { name: "Porównanie wartości: Mój portfel, A, B, C" });

    for (const name of ["A", "B", "C"]) await user.click(within(legend()).getByRole("button", { name }));
    expect(await screen.findByRole("img", { name: "Porównanie wartości: Mój portfel" })).toBeInTheDocument();

    await user.click(within(legend()).getByRole("button", { name: "Mój portfel" }));
    expect(screen.getByText("Wybierz linię na wykresie.")).toBeInTheDocument();
  });

  it("asks only the shown scenarios for another period", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator");
    await screen.findByRole("img", { name: /Porównanie wartości/ });

    await user.click(screen.getByRole("button", { name: "1R" }));
    await screen.findByRole("img", { name: /Porównanie wartości/ });
    const asked = new Set(fetchMock.mock.calls.map(([url]) => String(url))
      .filter((u) => u.includes("/result") && u.includes("period=1y")).map((u) => u.split("/")[3]));
    expect([...asked].sort()).toEqual(["1", "2", "3"]);
  });
});
