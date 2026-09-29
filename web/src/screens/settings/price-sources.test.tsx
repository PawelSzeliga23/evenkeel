import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIGNED_IN, json, mockFetch, renderApp, type MockRoute } from "../../test/render";
import { BROKEN, instrument } from "../../test/fixtures";

const GOOD = instrument({ id: 10, xtb_ticker: "SXR8.DE" });
const MANUAL = instrument({ id: 12, xtb_ticker: "VIE.FR", name: "Veolia", price_symbol: "VIE.PA", price_symbol_overridden: true });

function routes(sent: { id: string; body: unknown }[], answer?: () => Response): MockRoute[] {
  return [
    ...SIGNED_IN,
    { path: "/api/instruments", respond: () => [GOOD, MANUAL, BROKEN] },
    { method: "PATCH", path: /^\/api\/instruments\/\d+$/, respond: (url, init) => {
      sent.push({ id: url.pathname.split("/").pop()!, body: JSON.parse(String(init.body)) });
      return answer ? answer() : GOOD;
    } },
  ];
}

describe("price sources", () => {
  it("lists instruments with a problem first, with their symbol and state", async () => {
    mockFetch(routes([]));
    renderApp("/ustawienia/zrodla-cen");

    const rows = await screen.findAllByRole("button", { expanded: false });
    expect(rows.map((r) => r.querySelector("b")?.textContent)).toEqual(["EIMI.UK", "SXR8.DE", "VIE.FR"]);
    expect(within(rows[0]!).getByText("Dostawca nie zna symbolu EIMI.UK.")).toBeInTheDocument();
    expect(within(rows[1]!).getByText("Yahoo: SXR8.DE · ostatnia cena 26.09.2026")).toBeInTheDocument();
    expect(within(rows[2]!).getByText(/Yahoo: VIE\.PA \(ręczny\)/)).toBeInTheDocument();
  });

  it("saves a symbol typed by hand", async () => {
    const sent: { id: string; body: unknown }[] = [];
    mockFetch(routes(sent));
    const { user } = renderApp("/ustawienia/zrodla-cen");

    await user.click(await screen.findByRole("button", { name: /EIMI\.UK/ }));
    const input = screen.getByLabelText("Symbol w Yahoo");
    await user.clear(input);
    await user.type(input, "eimi.l");
    await user.click(screen.getByRole("button", { name: "Zapisz symbol" }));

    expect(await screen.findByText("Zapisano. Ceny pobiorę przy najbliższej aktualizacji.")).toBeInTheDocument();
    expect(sent).toEqual([{ id: "11", body: { price_symbol: "eimi.l" } }]);
  });

  it("restores the automatic symbol", async () => {
    const sent: { id: string; body: unknown }[] = [];
    mockFetch(routes(sent));
    const { user } = renderApp("/ustawienia/zrodla-cen");

    await user.click(await screen.findByRole("button", { name: /VIE\.FR/ }));
    await user.click(screen.getByRole("button", { name: "Przywróć automatyczny" }));

    expect(await screen.findByText("Zapisano. Ceny pobiorę przy najbliższej aktualizacji.")).toBeInTheDocument();
    expect(sent).toEqual([{ id: "12", body: { price_symbol: null } }]);
  });

  it("checks the symbol before asking the API and shows the API's refusal in Polish", async () => {
    const sent: { id: string; body: unknown }[] = [];
    mockFetch(routes(sent, () => json(422, { code: "validation_error", message: "Nieprawidłowe dane.",
      details: { errors: [{ loc: ["body", "price_symbol"], type: "string_pattern_mismatch" }] } })));
    const { user } = renderApp("/ustawienia/zrodla-cen");

    await user.click(await screen.findByRole("button", { name: /EIMI\.UK/ }));
    const input = screen.getByLabelText("Symbol w Yahoo");
    await user.clear(input);
    await user.click(screen.getByRole("button", { name: "Zapisz symbol" }));
    expect(await screen.findByText("Podaj symbol, np. EIMI.L.")).toBeInTheDocument();
    expect(sent).toEqual([]);

    await user.type(input, "EIMI L");
    await user.click(screen.getByRole("button", { name: "Zapisz symbol" }));
    expect(await screen.findByText("Symbol może zawierać litery, cyfry i znaki . - ^ =.")).toBeInTheDocument();
  });
});
