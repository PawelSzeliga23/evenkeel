import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, NETWORK_MESSAGE, getAccessToken, refreshSession, request, setAccessToken, setSessionExpiredHandler } from "./client";

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

let handler: Handler;
const calls: { url: string; init: RequestInit }[] = [];

beforeEach(() => {
  calls.length = 0;
  setAccessToken("old");
  setSessionExpiredHandler(() => {});
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return handler(url, init);
  }));
});

afterEach(() => vi.unstubAllGlobals());

const auth = (init: RequestInit) => new Headers(init.headers).get("Authorization");

describe("request", () => {
  it("sends the token, same-origin credentials and the query without empty values", async () => {
    handler = () => json(200, { ok: true });

    await expect(request("/api/positions", { query: { account_id: 3, date: null } })).resolves.toEqual({ ok: true });

    expect(calls[0]!.url).toBe("/api/positions?account_id=3");
    expect(calls[0]!.init.credentials).toBe("same-origin");
    expect(auth(calls[0]!.init)).toBe("Bearer old");
  });

  it("turns the API error format into an ApiError with the Polish message", async () => {
    handler = () => json(404, { code: "not_found", message: "Nie znaleziono.", details: { id: 7 } });

    const error = await request("/api/positions/1/2").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code: "not_found", message: "Nie znaleziono.", details: { id: 7 } });
  });

  it("reports a network failure in words, not as a crash", async () => {
    handler = () => Promise.reject(new TypeError("Failed to fetch"));

    await expect(request("/api/portfolio/summary")).rejects.toMatchObject({ code: "network", message: NETWORK_MESSAGE });
  });

  it("reports a gateway failure (the dev proxy answers 502 when the API is down) as a lost connection", async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    handler = () => new Response(null, { status: 502 });

    await expect(request("/api/portfolio/summary")).rejects.toMatchObject({ code: "network", message: NETWORK_MESSAGE });
    expect(expired).not.toHaveBeenCalled();
  });

  it("refreshes once for many parallel 401s and repeats each request with the new token", async () => {
    let refreshes = 0;
    handler = async (url, init) => {
      if (url === "/api/auth/refresh") {
        refreshes += 1;
        await new Promise((resolve) => setTimeout(resolve, 5));
        return json(200, { access_token: "new", token_type: "bearer" });
      }
      return auth(init) === "Bearer new" ? json(200, { url }) : json(401, { code: "unauthorized", message: "x", details: {} });
    };

    const results = await Promise.all(["/api/a", "/api/b", "/api/c"].map((path) => request<{ url: string }>(path)));

    expect(results.map((r) => r.url)).toEqual(["/api/a", "/api/b", "/api/c"]);
    expect(refreshes).toBe(1);
    expect(getAccessToken()).toBe("new");
  });

  it("calls the expiry handler when the refresh is refused", async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    handler = () => json(401, { code: "invalid_refresh", message: "Sesja wygasła.", details: {} });

    await expect(request("/api/portfolio/summary")).rejects.toMatchObject({ status: 401 });
    expect(expired).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
  });

  it("does not refresh for requests that do not use the session", async () => {
    handler = () => json(401, { code: "invalid_credentials", message: "Nieprawidłowy e-mail lub hasło.", details: {} });

    await expect(request("/api/auth/login", { method: "POST", json: {}, auth: false })).rejects.toMatchObject({
      code: "invalid_credentials",
    });
    expect(calls).toHaveLength(1);
  });

  it("sends JSON and multipart bodies and returns nothing for 204", async () => {
    handler = () => new Response(null, { status: 204 });
    const form = new FormData();
    form.append("files", new Blob(["x"]), "a.xlsx");

    await request("/api/x", { method: "POST", json: { a: 1 } });
    await request("/api/y", { method: "POST", form });

    expect(new Headers(calls[0]!.init.headers).get("Content-Type")).toBe("application/json");
    expect(calls[0]!.init.body).toBe('{"a":1}');
    expect(new Headers(calls[1]!.init.headers).get("Content-Type")).toBeNull();
    expect(calls[1]!.init.body).toBe(form);
  });
});

describe("refreshSession", () => {
  it("runs the refresh inside the cross-tab lock when the browser has one", async () => {
    const names: string[] = [];
    const locks = {
      request: vi.fn(async (name: string, callback: () => Promise<unknown>) => {
        names.push(name);
        return callback();
      }),
    };
    Object.defineProperty(navigator, "locks", { configurable: true, value: locks });
    try {
      handler = () => json(200, { access_token: "locked", token_type: "bearer" });
      await expect(refreshSession()).resolves.toBe(true);
      expect(names).toEqual(["portfolio-refresh"]);
      expect(getAccessToken()).toBe("locked");
    } finally {
      delete (navigator as unknown as { locks?: unknown }).locks;
    }
  });

  it("starts a fresh refresh after a failed one", async () => {
    handler = () => Promise.reject(new TypeError("Failed to fetch"));
    await expect(refreshSession()).rejects.toMatchObject({ code: "network" });
    handler = () => json(200, { access_token: "again", token_type: "bearer" });
    await expect(refreshSession()).resolves.toBe(true);
  });

  it("returns false and clears the token when there is no session", async () => {
    handler = () => json(401, { code: "invalid_refresh", message: "x", details: {} });
    await expect(refreshSession()).resolves.toBe(false);
    expect(getAccessToken()).toBeNull();
  });

  it("throws a network ApiError when the API cannot be reached", async () => {
    handler = () => Promise.reject(new TypeError("Failed to fetch"));
    await expect(refreshSession()).rejects.toMatchObject({ code: "network" });
  });

  it("throws network error when refresh answers 503", async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    handler = async (url) => {
      if (url === "/api/auth/refresh") {
        return new Response(null, { status: 503 });
      }
      return json(401, { code: "unauthorized", message: "x", details: {} });
    };

    await expect(request("/api/portfolio/summary")).rejects.toMatchObject({ code: "network", message: NETWORK_MESSAGE });
    expect(expired).not.toHaveBeenCalled();
    expect(getAccessToken()).toBe("old");
  });

  it("throws API error when refresh answers 500 with error JSON", async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    handler = async (url) => {
      if (url === "/api/auth/refresh") {
        return json(500, { code: "server_error", message: "Wewnętrzny błąd serwera.", details: {} });
      }
      return json(401, { code: "unauthorized", message: "x", details: {} });
    };

    await expect(request("/api/portfolio/summary")).rejects.toMatchObject({ code: "server_error", message: "Wewnętrzny błąd serwera." });
    expect(expired).not.toHaveBeenCalled();
    expect(getAccessToken()).toBe("old");
  });
});
