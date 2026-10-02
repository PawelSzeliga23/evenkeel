import { useQuery } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import type { RouteObject } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { NETWORK_MESSAGE, getAccessToken } from "../api/client";
import { api } from "../api/endpoints";
import { SIGNED_IN, USER, json, mockFetch, renderApp, renderRoutes, type MockRoute } from "../test/render";
import { LoginScreen } from "./LoginScreen";
import { RegisterScreen } from "./RegisterScreen";
import { GuestOnly, RequireAuth } from "./RequireAuth";
import { useSession } from "./session";

function Protected() {
  const { state } = useSession();
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => api.summary([]) });
  return <p>Witaj {state.status === "signedIn" ? state.user.email : ""} {summary.data ? "z danymi" : ""}</p>;
}

const ROUTES: RouteObject[] = [
  { element: <GuestOnly />, children: [{ path: "/logowanie", element: <LoginScreen /> }, { path: "/rejestracja", element: <RegisterScreen /> }] },
  { element: <RequireAuth />, children: [{ path: "/", element: <Protected /> }] },
];

const NO_SESSION: MockRoute = {
  method: "POST", path: "/api/auth/refresh", status: 401,
  respond: () => ({ code: "invalid_refresh", message: "Zaloguj się ponownie.", details: {} }),
};
const SUMMARY: MockRoute = { path: "/api/portfolio/summary", respond: () => ({ as_of: null }) };
const WELCOME = `Witaj ${USER.email} z danymi`;

describe("session", () => {
  it("sends a visitor without a session to the login screen", async () => {
    mockFetch([NO_SESSION]);
    renderRoutes(ROUTES, "/");
    expect(await screen.findByRole("heading", { name: "Evenkeel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zaloguj się" })).toBeInTheDocument();
  });

  it("restores the session from the refresh cookie", async () => {
    mockFetch([...SIGNED_IN, SUMMARY]);
    renderRoutes(ROUTES, "/");
    expect(await screen.findByText(WELCOME)).toBeInTheDocument();
  });

  it("logs in, shows the API's message on a wrong password and returns to the page asked for", async () => {
    let attempts = 0;
    mockFetch([
      NO_SESSION,
      {
        method: "POST", path: "/api/auth/login",
        respond: () => (++attempts === 1
          ? json(401, { code: "invalid_credentials", message: "Nieprawidłowy e-mail lub hasło.", details: {} })
          : { access_token: "token", token_type: "bearer" }),
      },
      { path: "/api/auth/me", respond: () => USER },
      SUMMARY,
    ]);
    const { user } = renderRoutes(ROUTES, "/");

    await user.type(await screen.findByLabelText("E-mail"), "anna@portfolio.dev");
    await user.type(screen.getByLabelText("Hasło"), "zle-haslo-123");
    await user.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Nieprawidłowy e-mail lub hasło.");

    await user.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByText(WELCOME)).toBeInTheDocument();
  });

  it("returns to the login screen with a note when the session expires", async () => {
    let refreshes = 0;
    mockFetch([
      {
        method: "POST", path: "/api/auth/refresh",
        respond: () => (++refreshes === 1
          ? { access_token: "token", token_type: "bearer" }
          : json(401, { code: "invalid_refresh", message: "x", details: {} })),
      },
      { path: "/api/auth/me", respond: () => USER },
      { path: "/api/portfolio/summary", status: 401, respond: () => ({ code: "unauthorized", message: "x", details: {} }) },
    ]);
    renderRoutes(ROUTES, "/");
    expect(await screen.findByText("Sesja wygasła, zaloguj się ponownie.")).toBeInTheDocument();
  });

  it("shows the connection problem full screen when the API is down at startup and retries on demand", async () => {
    const fetchMock = mockFetch([]);
    fetchMock.mockImplementation(() => Promise.reject(new TypeError("Failed to fetch")));
    const { user } = renderRoutes(ROUTES, "/");

    expect(await screen.findByRole("alert")).toHaveTextContent(NETWORK_MESSAGE);
    expect(screen.queryByLabelText("E-mail")).not.toBeInTheDocument();

    mockFetch([...SIGNED_IN, SUMMARY]);
    await user.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(await screen.findByText(WELCOME)).toBeInTheDocument();
  });

  it("shows the connection problem on the login form when the API goes down after the page opened", async () => {
    const fetchMock = mockFetch([NO_SESSION]);
    const { user } = renderRoutes(ROUTES, "/");
    await user.type(await screen.findByLabelText("E-mail"), "anna@portfolio.dev");
    await user.type(screen.getByLabelText("Hasło"), "haslo-123456");
    fetchMock.mockImplementation(() => Promise.reject(new TypeError("Failed to fetch")));
    await user.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(NETWORK_MESSAGE);
  });

  it("tells a server error at startup apart from a missing connection and retries on demand", async () => {
    mockFetch([{ method: "POST", path: "/api/auth/refresh", status: 500,
      respond: () => ({ code: "internal_error", message: "Błąd serwera.", details: {} }) }]);
    const { user } = renderRoutes(ROUTES, "/");

    expect(await screen.findByRole("alert")).toHaveTextContent("Serwer ma problem. Spróbuj ponownie za chwilę.");
    expect(screen.queryByText(NETWORK_MESSAGE)).not.toBeInTheDocument();

    mockFetch([...SIGNED_IN, SUMMARY]);
    await user.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(await screen.findByText(WELCOME)).toBeInTheDocument();
  });

  it("goes to the login screen when /me refuses the token right after a refresh", async () => {
    let refreshes = 0;
    mockFetch([
      { method: "POST", path: "/api/auth/refresh", respond: () => (++refreshes === 1
        ? { access_token: "token", token_type: "bearer" }
        : json(401, { code: "invalid_refresh", message: "Zaloguj się ponownie.", details: {} })) },
      { path: "/api/auth/me", status: 401, respond: () => ({ code: "invalid_token", message: "Zaloguj się ponownie.", details: {} }) },
    ]);
    renderRoutes(ROUTES, "/");

    expect(await screen.findByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.queryByText(NETWORK_MESSAGE)).not.toBeInTheDocument();
  });
});

describe("registration", () => {
  it("checks the password length before asking the API", async () => {
    const fetchMock = mockFetch([NO_SESSION]);
    const { user } = renderRoutes(ROUTES, "/rejestracja");

    await user.type(await screen.findByLabelText("E-mail"), "nowy@portfolio.dev");
    await user.type(screen.getByLabelText("Hasło"), "krotkie");
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Hasło musi mieć co najmniej 10 znaków.");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/register"))).toBe(false);
  });

  it("asks for an invite code only when the API requires one, then signs in", async () => {
    const bodies: Record<string, unknown>[] = [];
    mockFetch([
      NO_SESSION,
      {
        method: "POST", path: "/api/auth/register",
        respond: (_url, init) => {
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          bodies.push(body);
          return body.invite_code === "ZAPROSZENIE"
            ? json(201, USER)
            : json(403, { code: "invite_required", message: "Rejestracja wymaga ważnego kodu zaproszenia.", details: {} });
        },
      },
      { method: "POST", path: "/api/auth/login", respond: () => ({ access_token: "token", token_type: "bearer" }) },
      { path: "/api/auth/me", respond: () => USER },
      SUMMARY,
    ]);
    const { user } = renderRoutes(ROUTES, "/rejestracja");

    await user.type(await screen.findByLabelText("E-mail"), USER.email);
    expect(screen.queryByLabelText("Kod zaproszenia")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Hasło"), "dlugie-haslo-1");
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Rejestracja wymaga ważnego kodu zaproszenia.");
    await user.type(screen.getByLabelText("Kod zaproszenia"), "ZAPROSZENIE");
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));

    expect(await screen.findByText(WELCOME)).toBeInTheDocument();
    await waitFor(() => expect(bodies.at(-1)).toMatchObject({ email: USER.email, invite_code: "ZAPROSZENIE" }));
    expect(bodies[0]).not.toHaveProperty("invite_code");
  });
});

describe("sign-out", () => {
  it("signs out even when the server is down and says the server session will expire", async () => {
    mockFetch([...SIGNED_IN, { method: "POST", path: "/api/auth/logout", respond: () => { throw new TypeError("Failed to fetch"); } },
      { path: "/api/accounts", respond: () => [] }, { path: "/api/instruments", respond: () => [] }]);
    const { user } = renderApp("/ustawienia");

    await user.click(await screen.findByRole("button", { name: "Wyloguj" }));

    expect(await screen.findByText(
      "Wylogowano na tym urządzeniu. Serwer był niedostępny, więc sesja na serwerze wygaśnie sama.",
    )).toBeInTheDocument();
  });

  it("signs out when another tab signs out", async () => {
    if (typeof BroadcastChannel === "undefined") {
      const { BroadcastChannel: NodeChannel } = await import("node:worker_threads");
      vi.stubGlobal("BroadcastChannel", NodeChannel);
    }
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] }, { path: "/api/instruments", respond: () => [] }]);
    renderApp("/ustawienia");
    expect(await screen.findByRole("button", { name: "Wyloguj" })).toBeInTheDocument();

    const other = new BroadcastChannel("portfolio-session");
    other.postMessage("signed-out");
    other.close();

    expect(await screen.findByRole("button", { name: "Zaloguj się" })).toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});

describe("registration and session edge cases", () => {
  const REGISTER_INVITE: MockRoute = {
    method: "POST", path: "/api/auth/register", status: 403,
    respond: () => ({ code: "invite_required", message: "Rejestracja wymaga ważnego kodu zaproszenia.", details: {} }),
  };

  it("does not send an empty invite code", async () => {
    const fetchMock = mockFetch([NO_SESSION, REGISTER_INVITE]);
    const { user } = renderRoutes(ROUTES, "/rejestracja");
    await user.type(await screen.findByLabelText("E-mail"), USER.email);
    await user.type(screen.getByLabelText("Hasło"), "dlugie-haslo-1");
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));
    await screen.findByLabelText("Kod zaproszenia");

    await user.click(screen.getByRole("button", { name: "Załóż konto" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Podaj kod zaproszenia.");
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/register"))).toHaveLength(1);
  });

  it("sends to the login screen when the account was made but signing in failed", async () => {
    mockFetch([
      NO_SESSION,
      { method: "POST", path: "/api/auth/register", status: 201, respond: () => USER },
      { method: "POST", path: "/api/auth/login", status: 500, respond: () => ({ code: "internal_error", message: "Błąd serwera.", details: {} }) },
    ]);
    const { user } = renderRoutes(ROUTES, "/rejestracja");
    await user.type(await screen.findByLabelText("E-mail"), USER.email);
    await user.type(screen.getByLabelText("Hasło"), "dlugie-haslo-1");
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Konto zostało założone, ale nie udało się zalogować. Zaloguj się.");
    expect(screen.getByRole("link", { name: "Przejdź do logowania" })).toHaveAttribute("href", "/logowanie");
    expect(screen.queryByRole("button", { name: "Załóż konto" })).not.toBeInTheDocument();
  });

  it("goes to the login screen when the user behind the session no longer exists", async () => {
    mockFetch([
      { method: "POST", path: "/api/auth/refresh", respond: () => ({ access_token: "token", token_type: "bearer" }) },
      { path: "/api/auth/me", status: 404, respond: () => ({ code: "not_found", message: "Nie znaleziono.", details: {} }) },
    ]);
    renderRoutes(ROUTES, "/");

    expect(await screen.findByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.queryByText("Serwer ma problem. Spróbuj ponownie za chwilę.")).not.toBeInTheDocument();
  });

  it("drops the token when /me fails right after logging in", async () => {
    const fetchMock = mockFetch([
      NO_SESSION,
      { method: "POST", path: "/api/auth/login", respond: () => ({ access_token: "token", token_type: "bearer" }) },
      { path: "/api/auth/me", status: 500, respond: () => ({ code: "internal_error", message: "Błąd serwera.", details: {} }) },
    ]);
    const { user } = renderRoutes(ROUTES, "/logowanie");
    await user.type(await screen.findByLabelText("E-mail"), USER.email);
    await user.type(screen.getByLabelText("Hasło"), "dlugie-haslo-1");
    await user.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Błąd serwera.");

    await user.click(screen.getByRole("button", { name: "Zaloguj się" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/login"))).toHaveLength(2));
    const meCalls = fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/auth/me"));
    expect(new Headers(meCalls[0]![1]!.headers).get("Authorization")).toBe("Bearer token");
    expect(getAccessToken()).toBeNull();
  });
});
