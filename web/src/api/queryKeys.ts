/** TanStack Query keys. Everything valued starts with "portfolio", so one invalidation refreshes it all. */
export const keys = {
  accounts: ["accounts"] as const,
  portfolio: ["portfolio"] as const,
  summary: (accountId: number | null) => ["portfolio", "summary", accountId] as const,
  history: (accountId: number | null, from: string | null) => ["portfolio", "history", accountId, from] as const,
  exposure: (accountId: number | null, day: string) => ["portfolio", "exposure", accountId, day] as const,
  positions: (accountId: number | null) => ["portfolio", "positions", accountId] as const,
  position: (accountId: number, instrumentId: number) => ["portfolio", "position", accountId, instrumentId] as const,
};
