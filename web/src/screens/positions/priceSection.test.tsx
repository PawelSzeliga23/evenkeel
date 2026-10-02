import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { PriceChartData } from "../../api/types";
import { addMonths, todayIso } from "../../format";
import { DETAIL, PRICE_CHART } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";

const S = " ";
const PRICES = "/api/positions/2/12/prices";

function open(prices: PriceChartData = PRICE_CHART, detail = DETAIL) {
  const fetchMock = mockFetch([
    ...SIGNED_IN,
    { path: "/api/positions/2/12", respond: () => detail },
    // As the API: closes from `from` on, every operation of the position.
    { path: PRICES, respond: (url) => {
      const from = url.searchParams.get("from");
      return { ...prices, points: prices.points.filter((point) => from === null || point.date >= from) };
    } },
  ]);
  renderApp("/pozycje/2/12");
  const priceCalls = () => fetchMock.mock.calls.map(([input]) => new URL(input, "http://localhost"))
    .filter((url) => url.pathname === PRICES);
  return { priceCalls };
}

/** The section once its prices have arrived. */
async function section() {
  const box = await screen.findByRole("region", { name: "Wykres ceny" });
  await waitFor(() => expect(box.querySelector("[aria-busy]")).toBeNull());
  return box;
}

describe("Wykres ceny in the position details", () => {
  it("opens „Od zakupu”: asks from 14 days before the first purchase in the details", async () => {
    const { priceCalls } = open();

    const chart = within(await section()).getByRole("img", { name: /^Wykres ceny/ });

    expect(chart).toHaveAccessibleName("Wykres ceny od 29.04.2025 do 22.09.2026");
    expect(screen.getByRole("button", { name: "Od zakupu" })).toHaveAttribute("aria-pressed", "true");
    expect(priceCalls().map((url) => url.searchParams.get("from"))).toEqual(["2025-04-28"]);
  });

  it("asks again for each range, without `from` for Maks", async () => {
    const { priceCalls } = open();
    const box = await section();

    await userEvent.click(within(box).getByRole("button", { name: "1R" }));
    await waitFor(() => expect(priceCalls()).toHaveLength(2));
    await userEvent.click(within(box).getByRole("button", { name: "Maks" }));
    await waitFor(() => expect(priceCalls()).toHaveLength(3));

    expect(priceCalls().slice(1).map((url) => url.searchParams.get("from"))).toEqual([addMonths(todayIso(), -12), null]);
  });

  it("heads the section with the last close and the change since the first purchase, then within the range", async () => {
    open();
    const box = await section();

    expect(within(box).getByText("232,47 zł")).toBeInTheDocument();
    expect(within(box).getByText("+29,01 % od 1. zakupu")).toBeInTheDocument();

    await userEvent.click(within(box).getByRole("button", { name: "1R" }));

    expect(await within(box).findByText(/w zakresie$/)).toBeInTheDocument();
    expect(within(box).getByRole("button", { name: "1R" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows a purchase in the panel: quantity, price, amount paid and the change to today", async () => {
    open();
    const box = await section();

    await userEvent.click(within(box).getByRole("button", { name: `Zakup 12.05.2025, 30 szt. po 180,20${S}zł` }));

    const panel = within(box).getByRole("status");
    expect(panel).toHaveTextContent("Zakup, 12.05.2025");
    expect(panel).toHaveTextContent(`30 szt. po 180,20 zł · zapłacone 5 406,00 zł`);
    expect(panel).toHaveTextContent(`dziś +29,01 %`);
    expect(panel).not.toHaveTextContent("z przewalutowaniem");
  });

  it("adds the price with XTB's conversion for a foreign instrument and shows a dividend's amount", async () => {
    const foreign: PriceChartData = {
      ...PRICE_CHART, currency: "EUR",
      markers: [{ ...PRICE_CHART.markers[0]!, price_with_fx: "181.50" }, ...PRICE_CHART.markers.slice(1)],
    };
    open(foreign);
    const box = await section();

    await userEvent.click(within(box).getByRole("button", { name: /^Zakup 12\.05\.2025/ }));
    expect(within(box).getByRole("status")).toHaveTextContent(`z przewalutowaniem XTB 181,50 €`);

    await userEvent.click(within(box).getByRole("button", { name: /^Dywidenda/ }));
    expect(within(box).getByRole("status")).toHaveTextContent("Dywidenda, 20.06.2026");
    expect(within(box).getByRole("status")).toHaveTextContent("+60,00 zł");
  });

  it("draws the average purchase price, none for a closed position", async () => {
    open();
    expect(within(await section()).getByText("średnia 192,2338 zł")).toBeInTheDocument();
    cleanup();

    open(PRICE_CHART, { ...DETAIL, position: { ...DETAIL.position, quantity: "0" } });
    expect(within(await section()).getByRole("img", { name: /^Wykres ceny/ })).toBeInTheDocument();
    expect(screen.queryByText(/^średnia/)).not.toBeInTheDocument();
  });

  it("says when the instrument has no closes", async () => {
    open({ ...PRICE_CHART, points: [] });
    expect(within(await section()).getByText("Brak notowań dla tego instrumentu.")).toBeInTheDocument();
  });
});

