import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { refreshSession, setAccessToken, setSessionExpiredHandler } from "../api/client";
import { api } from "../api/endpoints";
import type { RegisterIn, UserOut } from "../api/types";

export type SessionState =
  | { status: "loading" }
  | { status: "anonymous"; expired: boolean }
  | { status: "signedIn"; user: UserOut };

interface Session {
  state: SessionState;
  signIn(email: string, password: string): Promise<void>;
  register(body: RegisterIn): Promise<void>;
  signOut(): Promise<void>;
}

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<SessionState>({ status: "loading" });

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
          return;
        }
      } catch {
        // no connection: the login screen says so on the first attempt
      }
      if (!cancelled) setState({ status: "anonymous", expired: false });
    })();
    return () => {
      cancelled = true;
    };
  }, [queryClient]);

  const signIn = useCallback(async (email: string, password: string) => {
    const token = await api.login(email, password);
    setAccessToken(token.access_token);
    const user = await api.me();
    setState({ status: "signedIn", user });
  }, []);

  const register = useCallback(async (body: RegisterIn) => {
    await api.register(body);
    await signIn(body.email, body.password);
  }, [signIn]);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setAccessToken(null);
      queryClient.clear();
      setState({ status: "anonymous", expired: false });
    }
  }, [queryClient]);

  const value = useMemo(() => ({ state, signIn, register, signOut }), [state, signIn, register, signOut]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession outside SessionProvider");
  return session;
}
