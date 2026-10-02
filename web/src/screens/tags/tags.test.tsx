import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { TagsReport } from "../../api/types";
import { ACCOUNTS, ANALYTICS, TAGS_REPORT } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";

const T = " ";

const SOME_TAGS = [{ id: 1, name: "USA", color: "#F0A43A", links: 1 }];

function routes(report: TagsReport = TAGS_REPORT, tags: unknown[] = SOME_TAGS) {
  return mockFetch([
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/analytics", respond: () => ANALYTICS },
    { path: "/api/analytics/tags", respond: () => report },
    { path: "/api/tags", respond: () => tags },
  ]);
}

const tagCalls = (fetchMock: ReturnType<typeof routes>) => fetchMock.mock.calls
  .map(([input]) => new URL(String(input), "http://localhost")).filter((url) => url.pathname === "/api/analytics/tags");
const line = (key: string) => document.querySelector(`path[data-line="${key}"]`);

describe("Analiza → Tagi", () => {
  it("lists the tags in the API's order, then „bez tagu” and cash, with the note about 100 %", async () => {
    routes();
    renderApp("/analiza/tagi");

    const list = await screen.findByRole("list", { name: "Udział w portfelu" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows.map((row) => row.querySelector("b")?.textContent)).toEqual(["USA", "emerytura", "bez tagu", "Gotówka"]);
    expect(rows[0]).toHaveTextContent(`46,97${T}%`);
    expect(rows[0]).toHaveTextContent("1 walor");
    expect(rows[0]).toHaveTextContent(`4${T}697,00${T}zł`);
    expect(rows[0]).toHaveTextContent(`+804,20${T}zł`);
    expect(rows[0]).toHaveTextContent(`+18,68${T}%`);
    expect(rows[1]).toHaveTextContent("4 walory");
    expect(rows[2]).toHaveTextContent("2 walory");
    expect(rows[3]).toHaveTextContent(`13,03${T}%`);
    expect(screen.getByText("Walor z kilkoma tagami liczy się w każdym z nich, więc udziały nie sumują się do 100 %."))
      .toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Wartość portfela" })).toHaveTextContent(/10.000,00.zł/);
  });

  it("asks for the whole history first, then the chosen period, for the chosen accounts", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/tagi");

    await screen.findByRole("list", { name: "Udział w portfelu" });
    await user.click(screen.getByRole("button", { name: "Rok" }));

    await waitFor(() => expect(tagCalls(fetchMock).map((url) => url.searchParams.get("period"))).toEqual(["all", "1y"]));
  });

  it("draws a line per tag in its colour, „bez tagu” off, and hides a line from the legend", async () => {
    routes();
    const { user } = renderApp("/analiza/tagi");

    const legend = await screen.findByRole("group", { name: "Linie na wykresie" });
    expect(line("1")).toHaveAttribute("stroke", "#F0A43A");
    expect(line("2")).toHaveAttribute("stroke", "#7FB6E6");
    expect(line("untagged")).toBeNull();
    expect(within(legend).getByRole("button", { name: "bez tagu" })).toHaveAttribute("aria-pressed", "false");
    await user.click(within(legend).getByRole("button", { name: "USA" }));

    expect(line("1")).toBeNull();
    expect(within(legend).getByRole("button", { name: "USA" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("Liczone z obecnymi tagami na całej historii.")).toBeInTheDocument();
  });

  it("invites to add tags when there are none, without a chart", async () => {
    routes({ ...TAGS_REPORT, tags: [] }, []);
    renderApp("/analiza/tagi");

    expect(await screen.findByText("Nie masz jeszcze tagów. Dodasz je w szczegółach pozycji.")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Linie na wykresie" })).toBeNull();
  });
});

describe("Tagi card on Analiza", () => {
  const four: TagsReport = {
    ...TAGS_REPORT,
    tags: [
      ...TAGS_REPORT.tags,
      { ...TAGS_REPORT.tags[1]!, id: 3, name: "Polska", share_pct: "8.00" },
      { ...TAGS_REPORT.tags[1]!, id: 4, name: "spekulacja", share_pct: "2.00" },
    ],
  };

  it("shows the three largest tags with their shares and a link", async () => {
    routes(four);
    renderApp("/analiza");

    const card = await screen.findByRole("region", { name: "Tagi" });
    expect(await within(card).findByText("USA")).toBeInTheDocument();
    expect(within(card).getByText("Polska")).toBeInTheDocument();
    expect(within(card).queryByText("spekulacja")).toBeNull();
    expect(within(card).getByText(`46,97${T}%`)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Tagi" })).toHaveAttribute("href", "/analiza/tagi");
  });

  it("invites to add tags without a link when there are none", async () => {
    routes({ ...TAGS_REPORT, tags: [] }, []);
    renderApp("/analiza");

    const card = await screen.findByRole("region", { name: "Tagi" });
    expect(await within(card).findByText("Nie masz jeszcze tagów. Dodasz je w szczegółach pozycji.")).toBeInTheDocument();
    expect(within(card).queryByRole("link")).toBeNull();
  });
});

describe("tags without value in the chosen accounts", () => {
  it("says so on Analiza → Tagi and still shows the total and cash", async () => {
    routes({ ...TAGS_REPORT, tags: [] });
    renderApp("/analiza/tagi");

    expect(await screen.findByText("Żaden tag nie ma wartości na wybranych kontach.")).toBeInTheDocument();
    expect(screen.queryByText("Nie masz jeszcze tagów. Dodasz je w szczegółach pozycji.")).toBeNull();
    const rows = within(screen.getByRole("list", { name: "Udział w portfelu" })).getAllByRole("listitem");
    expect(rows.map((row) => row.querySelector("b")?.textContent)).toEqual(["bez tagu", "Gotówka"]);
  });

  it("says so on the card", async () => {
    routes({ ...TAGS_REPORT, tags: [] });
    renderApp("/analiza");

    const card = await screen.findByRole("region", { name: "Tagi" });
    expect(await within(card).findByText("Żaden tag nie ma wartości na wybranych kontach.")).toBeInTheDocument();
  });
});
