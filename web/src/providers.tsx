import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ApiError } from "./api/client";
import { SessionProvider } from "./auth/session";

/** Retries only what may heal by itself (no connection, server errors); never 4xx. */
export function createQueryClient({ test = false }: { test?: boolean } = {}): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: !test,
        retry: test ? false : (count, error) => error instanceof ApiError && (error.status === 0 || error.status >= 500) && count < 2,
      },
      mutations: { retry: false },
    },
  });
}

export function AppProviders({ client, children }: { client: QueryClient; children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <SessionProvider>{children}</SessionProvider>
    </QueryClientProvider>
  );
}
