import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIGNED_IN, json, mockFetch, renderApp, type MockRoute } from "../../test/render";

function routes(sent: unknown[], answer: () => Response = () => json(204, undefined)): MockRoute[] {
  return [
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => [] },
    { path: "/api/instruments", respond: () => [] },
    { method: "POST", path: "/api/auth/password", respond: (_u, init) => { sent.push(JSON.parse(String(init.body))); return answer(); } },
  ];
}

describe("password change", () => {
  it("changes the password and returns to the settings with a note", async () => {
    const sent: unknown[] = [];
    mockFetch(routes(sent));
    const { user, router } = renderApp("/ustawienia/haslo");

    await user.type(await screen.findByLabelText("Obecne hasło"), "bardzo-tajne-haslo");
    await user.type(screen.getByLabelText("Nowe hasło"), "jeszcze-bardziej-tajne");
    await user.type(screen.getByLabelText("Powtórz nowe hasło"), "jeszcze-bardziej-tajne");
    await user.click(screen.getByRole("button", { name: "Zmień hasło" }));

    expect(await screen.findByText("Hasło zmienione. Inne urządzenia zostaną wylogowane.")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/ustawienia");
    expect(sent).toEqual([{ current_password: "bardzo-tajne-haslo", new_password: "jeszcze-bardziej-tajne" }]);
  });

  it("checks the new password before asking the API", async () => {
    const sent: unknown[] = [];
    mockFetch(routes(sent));
    const { user } = renderApp("/ustawienia/haslo");

    await user.type(await screen.findByLabelText("Obecne hasło"), "bardzo-tajne-haslo");
    await user.type(screen.getByLabelText("Nowe hasło"), "krotkie");
    await user.type(screen.getByLabelText("Powtórz nowe hasło"), "inne");
    await user.click(screen.getByRole("button", { name: "Zmień hasło" }));

    expect(await screen.findByText("Hasło musi mieć co najmniej 10 znaków.")).toBeInTheDocument();
    expect(screen.getByText("Hasła różnią się.")).toBeInTheDocument();
    expect(sent).toEqual([]);
  });

  it("shows a wrong current password at its field and keeps what was typed", async () => {
    const sent: unknown[] = [];
    mockFetch(routes(sent, () => json(400, { code: "wrong_password", message: "Obecne hasło jest nieprawidłowe.", details: {} })));
    const { user } = renderApp("/ustawienia/haslo");

    await user.type(await screen.findByLabelText("Obecne hasło"), "zle-haslo-123");
    await user.type(screen.getByLabelText("Nowe hasło"), "jeszcze-bardziej-tajne");
    await user.type(screen.getByLabelText("Powtórz nowe hasło"), "jeszcze-bardziej-tajne");
    await user.click(screen.getByRole("button", { name: "Zmień hasło" }));

    expect(await screen.findByText("Obecne hasło jest nieprawidłowe.")).toBeInTheDocument();
    expect(screen.getByLabelText("Nowe hasło")).toHaveValue("jeszcze-bardziej-tajne");
  });
});
