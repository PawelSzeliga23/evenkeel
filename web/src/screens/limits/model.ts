import type { Limit, Money } from "../../api/types";
import { fromCents, toCents } from "../../format";

export const WRAPPER_LABEL: Record<Limit["wrapper"], string> = { ike: "IKE", ikze: "IKZE" };

/** The API lists each wrapper newest year first. */
export function byWrapper(limits: Limit[]): { wrapper: Limit["wrapper"]; current: Limit; earlier: Limit[] }[] {
  return (["ike", "ikze"] as const).flatMap((wrapper) => {
    const years = limits.filter((l) => l.wrapper === wrapper).sort((a, b) => b.year - a.year);
    return years.length ? [{ wrapper, current: years[0]!, earlier: years.slice(1) }] : [];
  });
}

/** Display proportion of the bar (0–1); null without a limit for that year. */
export function filled(limit: Limit): number | null {
  if (limit.limit_pln === null || toCents(limit.limit_pln) <= 0n) return null;
  return Math.min(Number(limit.paid_pln) / Number(limit.limit_pln), 1);
}

export function overBy(limit: Limit): Money | null {
  if (!limit.exceeded || limit.limit_pln === null) return null;
  return fromCents(toCents(limit.paid_pln) - toCents(limit.limit_pln));
}
