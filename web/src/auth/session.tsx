import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, refreshSession, setAccessToken, setSessionExpiredHandler } from "../api/client";
import { api } from "../api/endpoints";
import type { RegisterIn, UserOut } from "../api/types";

export type SessionState =
  | { status: "loading" }
  | { status: "offline" }
  | { status: "serverError" }
  | { status: "anonymous"; expired: boolean; offlineLogout?: boolean }
  | { status: "signedIn"; user: UserOut };

interface Session {
  state: SessionState;
  signIn(email: string, password: string): Promise<void>;
  register(body: RegisterIn): Promise<void>;
  signOut(): Promise<void>;
  /** runs the startup restore again after it failed (no connection or a server error) */
  retry(): void;
}

export const SESSION_CHANNEL = "portfolio-session";

function announceSignOut() {
  if (typeof BroadcastChannel === "undefined") return;
  const channel = new BroadcastChannel(SESSION_CHANNEL);
  channel.postMessage("signed-out");
  channel.close();
}

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<SessionState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      setAccessToken(null);
      queryClient.clear();
      setState({ status: "anonymous", expired: true });
    });
    let cancelled = false;
    (async () => {
      try {
        if (await refreshSession()) {
          const user = await api.me();
          if (!cancelled) setState({ status: "signedIn", user });
        } else if (!cancelled) {
          setState({ status: "anonymous", expired: false });
        }
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          setAccessToken(null);
          setState({ status: "anonymous", expired: false });
        } else if (error instanceof ApiError && error.status !== 0) {
          setState({ status: "serverError" });
        } else {
          setState({ status: "offline" });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [queryClient, attempt]);

  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    const channel = new BroadcastChannel(SESSION_CHANNEL);
    channel.onmessage = (event) => {
      if (event.data !== "signed-out") return;
      setAccessToken(null);
      queryClient.clear();
      // the tab that signed out also hears its own message: keep its state (expired / offlineLogout notices)
      setState((current) => (current.status === "anonymous" ? current : { status: "anonymous", expired: false }));
    };
    return () => channel.close();
  }, [queryClient]);

  const retry = useCallback(() => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const token = await api.login(email, password);
    setAccessToken(token.access_token);
    let user: UserOut;
    try {
      user = await api.me();
    } catch (error) {
      setAccessToken(null);
      throw error;
    }
    setState({ status: "signedIn", user });
  }, []);

  const register = useCallback(async (body: RegisterIn) => {
    await api.register(body);
    await signIn(body.email, body.password);
  }, [signIn]);

  const signOut = useCallback(async () => {
    let offline = false;
    try {
      await api.logout();
    } catch {
      offline = true; // the refresh cookie stays valid on the server until it expires
    }
    setAccessToken(null);
    queryClient.clear();
    announceSignOut();
    setState({ status: "anonymous", expired: false, offlineLogout: offline });
  }, [queryClient]);

  const value = useMemo(() => ({ state, signIn, register, signOut, retry }), [state, signIn, register, signOut, retry]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession outside SessionProvider");
  return session;
}
