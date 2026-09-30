/** The only place that talks HTTP: bearer token in memory, one refresh at a time, API errors as ApiError. */

export const NETWORK_MESSAGE = "Brak połączenia z serwerem. Sprawdź, czy API działa, i spróbuj ponownie.";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let accessToken: string | null = null;
let onSessionExpired: () => void = () => {};
let refreshing: Promise<boolean> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setSessionExpiredHandler(handler: () => void): void {
  onSessionExpired = handler;
}

const networkError = () => new ApiError(0, "network", NETWORK_MESSAGE);

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { code?: string; message?: string; details?: Record<string, unknown> };
    if (body.code && body.message) return new ApiError(response.status, body.code, body.message, body.details ?? {});
  } catch {
    // not the API's JSON error format
  }
  return new ApiError(response.status, "http_error", `Serwer odpowiedział błędem ${response.status}. Spróbuj ponownie.`);
}

function isGatewayFailure(response: Response): boolean {
  return response.status === 502 || response.status === 503 || response.status === 504;
}

async function doRefresh(): Promise<boolean> {
  let response: Response;
  try {
    response = await fetch("/api/auth/refresh", { method: "POST", credentials: "same-origin" });
  } catch {
    throw networkError();
  }
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      accessToken = null;
      return false;
    }
    if (isGatewayFailure(response)) throw networkError();
    throw await toApiError(response);
  }
  accessToken = ((await response.json()) as { access_token: string }).access_token;
  return true;
}

/**
 * Exchanges the httpOnly refresh cookie for a new access token. Concurrent callers share one request, and
 * tabs take turns (the API treats a reused, already rotated refresh token as theft and ends every session).
 */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    const locks = typeof navigator === "undefined" ? undefined : navigator.locks;
    return locks ? locks.request("portfolio-refresh", doRefresh) : doRefresh();
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

type Query = Record<string, string | number | readonly number[] | null | undefined>;

export interface RequestOptions {
  method?: string;
  query?: Query;
  json?: unknown;
  form?: FormData;
  /** false for login, register and logout: a 401 there is an answer, not an expired session */
  auth?: boolean;
}

function withQuery(path: string, query: Query | undefined): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (Array.isArray(value)) for (const item of value) params.append(key, String(item));
    else if (value !== null && value !== undefined && value !== "") params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `${path}?${text}` : path;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = withQuery(path, options.query);
  const useSession = options.auth !== false;
  let sentWith: string | null = null;
  const send = async () => {
    const headers = new Headers();
    if (options.json !== undefined) headers.set("Content-Type", "application/json");
    sentWith = accessToken;
    if (useSession && accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    try {
      return await fetch(url, {
        method: options.method ?? "GET",
        credentials: "same-origin",
        headers,
        body: options.form ?? (options.json !== undefined ? JSON.stringify(options.json) : undefined),
      });
    } catch {
      throw networkError();
    }
  };

  const sendChecked = async () => {
    const result = await send();
    if (isGatewayFailure(result)) throw networkError();
    return result;
  };

  let response = await sendChecked();
  if (response.status === 401 && useSession) {
    if (accessToken !== null && accessToken !== sentWith) {
      response = await sendChecked(); // another request refreshed the session meanwhile
    } else if (await refreshSession()) {
      response = await sendChecked();
    } else {
      onSessionExpired();
      throw await toApiError(response);
    }
  }
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
