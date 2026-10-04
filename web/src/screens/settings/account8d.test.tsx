import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { describeDevice } from "../../auth/device";
import { searchSettings } from "../../settings/registry";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";

const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1";
const SESSIONS = [
  { id: "a", user_agent: IPHONE, started_at: "2026-10-02T08:00:00Z", last_used_at: "2026-10-04T12:30:00Z", current: true },
  { id: "b", user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
    started_at: "2026-09-20T08:00:00Z", last_used_at: "2026-10-03T18:00:00Z", current: false },
];

describe("describeDevice", () => {
  it.each([
    [IPHONE, "iPhone · Safari"],
    ["Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36", "Android · Chrome"],
    ["Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/130.0 Safari/537.36 Edg/130.0", "Windows · Edge"],
    ["Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0; rv:131.0) Gecko/20100101 Firefox/131.0", "Mac · Firefox"],
    ["Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) CriOS/130.0 Mobile Safari/604.1", "iPhone · Chrome"],
    ["curl/8.0", "Przeglądarka"],
    [null, "Nieznane urządzenie"],
  ])("%s → %s", (agent, label) => {
    expect(describeDevice(agent)).toBe(label);
  });
});

describe("Sesje i urządzenia", () => {
  it("lists this device first and signs out another one or all others", async () => {
    const calls: string[] = [];
    mockFetch([...SIGNED_IN, { path: "/api/auth/sessions", respond: () => SESSIONS },
      { method: "DELETE", path: "/api/auth/sessions/b", respond: () => { calls.push("one"); return json(204, undefined); } },
      { method: "POST", path: "/api/auth/sessions/revoke-others", respond: () => { calls.push("others"); return json(204, undefined); } }]);
    const { user } = renderApp("/ustawienia/sesje");

    const list = await screen.findByRole("list", { name: "Sesje" });
    const [mine, other] = within(list).getAllByRole("listitem");
    expect(mine).toHaveTextContent("iPhone · Safari");
    expect(mine).toHaveTextContent("To urządzenie");
    expect(within(mine!).queryByRole("button")).not.toBeInTheDocument();
    expect(other).toHaveTextContent("Windows · Chrome");
    expect(other).toHaveTextContent("Zalogowano 20.09.2026");

    await user.click(within(other!).getByRole("button", { name: "Wyloguj Windows · Chrome" }));
    await user.click(screen.getByRole("button", { name: "Wyloguj wszystkie inne" }));

    expect(calls).toEqual(["one", "others"]);
  });
});

describe("Usuń konto", () => {
  it("asks for the password and the phrase, then opens the login with a notice", async () => {
    const sent: unknown[] = [];
    mockFetch([...SIGNED_IN, { method: "DELETE", path: "/api/auth/account",
      respond: (_url, init) => { sent.push(JSON.parse(init.body as string)); return json(204, undefined); } }]);
    const { user } = renderApp("/ustawienia/usun-konto");

    const remove = await screen.findByRole("button", { name: "Usuń konto" });
    expect(screen.getByText(/Tego nie da się cofnąć/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pobierz kopię" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Hasło"), "bardzo-tajne-haslo");
    expect(remove).toBeDisabled();
    await user.type(screen.getByLabelText("Wpisz USUŃ KONTO"), "USUŃ KONTO");
    await user.click(remove);

    expect(await screen.findByText("Konto zostało usunięte.")).toBeInTheDocument();
    expect(sent).toEqual([{ password: "bardzo-tajne-haslo", confirm: "USUŃ KONTO" }]);
  });

  it("shows a wrong password and keeps the user signed in", async () => {
    mockFetch([...SIGNED_IN, { method: "DELETE", path: "/api/auth/account",
      respond: () => json(400, { code: "wrong_password", message: "Hasło jest nieprawidłowe.", details: {} }) }]);
    const { user } = renderApp("/ustawienia/usun-konto");

    await user.type(await screen.findByLabelText("Hasło"), "zle");
    await user.type(screen.getByLabelText("Wpisz USUŃ KONTO"), "USUŃ KONTO");
    await user.click(screen.getByRole("button", { name: "Usuń konto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Hasło jest nieprawidłowe.");
    expect(screen.getByRole("heading", { name: "Usuń konto" })).toBeInTheDocument();
  });

  it("is reached from Profil and found by the search", async () => {
    mockFetch([...SIGNED_IN]);
    renderApp("/ustawienia/profil");

    expect(await screen.findByRole("link", { name: "Sesje i urządzenia" })).toHaveAttribute("href", "/ustawienia/sesje");
    expect(screen.getByRole("link", { name: "Usuń konto" })).toHaveAttribute("href", "/ustawienia/usun-konto");
    expect(searchSettings("urządzenia", [], []).map((h) => h.title)).toEqual(["Sesje i urządzenia"]);
    expect(searchSettings("skasuj", [], []).map((h) => h.title)).toEqual(["Usuń konto"]);
  });
});
