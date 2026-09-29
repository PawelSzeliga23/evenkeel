import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter, type RouteObject } from "react-router";
import { vi } from "vitest";
import { AppProviders, createQueryClient } from "../providers";
import { appRoutes } from "../routes";

export interface MockRoute {
  method?: string;
  path: string | RegExp;
  respond: (url: URL, init: RequestInit) => unknown;
  status?: number;
}

export function json(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Stubs fetch with a routing table; an unmatched request answers 404 in the API's error format. */
export function mockFetch(routes: MockRoute[]) {
  const fetchMock = vi.fn(async (input: string, init: RequestInit = {}): Promise<Response> => {
    const url = new URL(input, "http://localhost");
    const method = init.method ?? "GET";
    const route = routes.find(
      (r) => (r.method ?? "GET") === method && (typeof r.path === "string" ? url.pathname === r.path : r.path.test(url.pathname)),
    );
    if (!route) return json(404, { code: "not_found", message: "Nie znaleziono.", details: {} });
    const out = await route.respond(url, init);
    return out instanceof Response ? out : json(route.status ?? 200, out);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const USER = { id: 1, email: "anna@portfolio.dev", base_currency: "PLN" };

/** A signed-in session: the refresh cookie is valid and /me answers. */
export const SIGNED_IN: MockRoute[] = [
  { method: "POST", path: "/api/auth/refresh", respond: () => ({ access_token: "token", token_type: "bearer" }) },
  { path: "/api/auth/me", respond: () => USER },
];

export function renderRoutes(routes: RouteObject[], path = "/") {
  const client = createQueryClient({ test: true });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const user = userEvent.setup();
  render(
    <AppProviders client={client}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { user, router, client };
}

export function renderApp(path = "/") {
  return renderRoutes(appRoutes, path);
}
