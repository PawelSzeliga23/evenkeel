import { useQuery } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import type { RouteObject } from "react-router";
import { describe, expect, it } from "vitest";
import { NETWORK_MESSAGE } from "../api/client";
import { api } from "../api/endpoints";
import { SIGNED_IN, USER, json, mockFetch, renderRoutes, type MockRoute } from "../test/render";
import { LoginScreen } from "./LoginScreen";
import { RegisterScreen } from "./RegisterScreen";
import { GuestOnly, RequireAuth } from "./RequireAuth";
import { useSession } from "./session";

function Protected() {
  const { state } = useSession();
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => api.summary(null) });
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
    expect(await screen.findByRole("heading", { name: "Portfel" })).toBeInTheDocument();
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

  it("shows the connection problem instead of failing silently when the API is down", async () => {
    const fetchMock = mockFetch([]);
    fetchMock.mockImplementation(() => Promise.reject(new TypeError("Failed to fetch")));
    const { user } = renderRoutes(ROUTES, "/");

    await user.type(await screen.findByLabelText("E-mail"), "anna@portfolio.dev");
    await user.type(screen.getByLabelText("Hasło"), "haslo-123456");
    await user.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(NETWORK_MESSAGE);
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
