import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, ANALYTICS, HOLDINGS, HOLDINGS_EMPTY } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";

function routes(answer: (url: URL) => unknown = () => HOLDINGS) {
  return mockFetch([
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/analytics", respond: () => ANALYTICS },
    { path: "/api/analytics/holdings", respond: answer },
  ]);
}

const ranking = () => within(screen.getByRole("list", { name: "Ranking" })).getAllByRole("listitem");

describe("Walory", () => {
  it("asks for the whole history by default (plan 8a) and for the chosen period", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/walory");

    expect(await screen.findByRole("heading", { name: "Walory" })).toBeInTheDocument();
    await screen.findByRole("button", { name: /^SXR8, / });
    expect(screen.getByRole("button", { name: "Wszystko" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Rok" }));
    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls.some((u) => u.includes("/api/analytics/holdings") && u.includes("period=all"))).toBe(true);
    expect(urls.some((u) => u.includes("/api/analytics/holdings") && u.includes("period=1y"))).toBe(true);
  });

  it("shows a holding's details with the accounts after a tap on its tile", async () => {
    routes();
    const { user } = renderApp("/analiza/walory");

    await user.click(await screen.findByRole("button", { name: /^SXR8, \+0,91\s%$/ }));

    const details = screen.getByRole("region", { name: "SXR8.DE — Core S&P 500" });
    expect(details).toHaveTextContent("+13,49 zł");
    expect(details).toHaveTextContent("1 519,87 zł");
    expect(details).toHaveTextContent("IKE: +13,49 zł");
  });

  it("ranks by the gain in zł or in %", async () => {
    routes();
    const { user } = renderApp("/analiza/walory");

    await screen.findByRole("list", { name: "Ranking" });
    expect(ranking().map((row) => row.textContent?.slice(0, 4))).toEqual(["SXR8", "VIE ", "Trad", "EDO0", "SNT "]);
    await user.click(screen.getByRole("button", { name: "%" }));
    expect(ranking().map((row) => row.textContent?.slice(0, 4))).toEqual(["VIE ", "SXR8", "EDO0", "Trad", "SNT "]);
  });

  it("hides savings and bonds on request and shares out the rest among what is shown", async () => {
    routes();
    const { user } = renderApp("/analiza/walory");

    await screen.findByRole("list", { name: "Ranking" });
    expect(ranking()[0]).toHaveTextContent("11,4 % portfela · 86,5 % zysku");
    await user.click(screen.getByRole("checkbox", { name: "Bez oszczędności i obligacji" }));

    expect(ranking()).toHaveLength(3);
    expect(ranking()[0]).toHaveTextContent("83,8 % portfela · 96,6 % zysku");
    expect(screen.queryByRole("button", { name: /^Trade Republic, / })).toBeNull();
    expect(screen.queryByRole("button", { name: /^EDO0935, / })).toBeNull();
    expect(within(screen.getByRole("table", { name: "Zysk według typów" })).getByText("Oszczędności")).toBeInTheDocument();
  });

  it("closes a holding's details when the toggle hides it", async () => {
    routes();
    const { user } = renderApp("/analiza/walory");

    await user.click(await screen.findByRole("button", { name: /^EDO0935, / }));
    expect(screen.getByRole("region", { name: "EDO0935" })).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Bez oszczędności i obligacji" }));
    await user.click(screen.getByRole("checkbox", { name: "Bez oszczędności i obligacji" }));

    expect(screen.queryByRole("region", { name: "EDO0935" })).toBeNull();
  });

  it("shows the gains by account and by kind", async () => {
    routes();
    renderApp("/analiza/walory");

    const accounts = await screen.findByRole("table", { name: "Zysk według kont" });
    expect(within(accounts).getByRole("row", { name: /^IKE 1\s619,87\szł \+11,66\szł \+0,72\s%$/ })).toBeInTheDocument();
    const kinds = screen.getByRole("table", { name: "Zysk według typów" });
    expect(within(kinds).getByRole("row", { name: /^ETF 1\s519,87\szł \+13,49\szł \+0,91\s%$/ })).toBeInTheDocument();
  });

  it("says when there is no valuation yet", async () => {
    routes(() => HOLDINGS_EMPTY);
    renderApp("/analiza/walory");

    expect(await screen.findByText("Nie ma jeszcze wyceny do pokazania.")).toBeInTheDocument();
  });

  it("shows a small day map on Analiza with a way to Walory", async () => {
    routes();
    const { user } = renderApp("/analiza");

    const card = await screen.findByRole("region", { name: "Walory" });
    expect(await within(card).findByRole("button", { name: /^SXR8, / })).toBeInTheDocument();
    await user.click(within(card).getByRole("link", { name: "Walory" }));
    expect(await screen.findByRole("heading", { name: "Walory", level: 1 })).toBeInTheDocument();
  });
});
