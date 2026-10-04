import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ACCOUNTS, EXPOSURE, HISTORY, LIMITS, POSITIONS, SUMMARY } from "../test/fixtures";
import { SIGNED_IN, USER, mockFetch, renderApp } from "../test/render";

afterEach(() => sessionStorage.clear());

function dashboard() {
  mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/portfolio/summary", respond: () => SUMMARY }, { path: "/api/portfolio/history", respond: () => HISTORY },
    { path: "/api/portfolio/exposure", respond: () => EXPOSURE }, { path: "/api/positions", respond: () => POSITIONS },
    { path: "/api/portfolio/limits", respond: () => LIMITS }]);
}

describe("hidden amounts", () => {
  it("hide every amount behind the eye on Pulpit and keep the percentages", async () => {
    dashboard();
    const { user } = renderApp("/");
    const eye = await screen.findByRole("button", { name: "Ukryj kwoty" });
    await screen.findAllByText(/zł/);

    await user.click(eye);

    expect(screen.getByRole("button", { name: "Pokaż kwoty" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText(/••••/).length).toBeGreaterThan(0));
    expect(screen.queryByText(/\d,\d\d\s?zł/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/%/).length).toBeGreaterThan(0);
    expect(localStorage.getItem("evenkeel.hideAmounts")).toBe("true");
  });

  it("are switched in Wygląd i prywatność, and the add form still shows what is typed", async () => {
    localStorage.setItem("evenkeel.hideAmounts", "true");
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] }]);
    const { user } = renderApp("/ustawienia/wyglad");

    expect(await screen.findByRole("switch", { name: "Ukrywaj kwoty" })).toBeChecked();
    await user.click(screen.getByRole("switch", { name: "Ukrywaj kwoty" }));
    expect(localStorage.getItem("evenkeel.hideAmounts")).toBe("false");
  });
});

describe("start screen", () => {
  it("opens the chosen screen once per tab session", async () => {
    mockFetch([...SIGNED_IN.filter((r) => r.path !== "/api/auth/me"),
      { path: "/api/auth/me", respond: () => ({ ...USER, preferences: { start_screen: "analysis" } }) },
      { path: "/api/accounts", respond: () => [] }]);
    const { router } = renderApp("/");

    await waitFor(() => expect(router.state.location.pathname).toBe("/analiza"));
    await router.navigate("/");
    expect(router.state.location.pathname).toBe("/");
  });

  it("is chosen in Wygląd i prywatność", async () => {
    mockFetch([...SIGNED_IN, { method: "PATCH", path: "/api/me/preferences",
      respond: (_u, init) => ({ start_screen: JSON.parse(String(init.body)).start_screen }) }]);
    const { user } = renderApp("/ustawienia/wyglad");

    await user.selectOptions(await screen.findByLabelText("Ekran startowy"), "positions");
    expect(await screen.findByRole("status")).toHaveTextContent("Zapisano.");
  });
});

describe("hidden amounts in forms", () => {
  it("leave what is typed in a form visible", async () => {
    localStorage.setItem("evenkeel.hideAmounts", "true");
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS }]);
    const { user } = renderApp("/dodaj/operacja");

    const amount = await screen.findByLabelText("Kwota");
    await user.type(amount, "1234,56");

    expect(amount).toHaveValue("1234,56");
  });
});
