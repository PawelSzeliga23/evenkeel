import type { Exposure, Position, Summary } from "../../api/types";
import { addMonths, toCents } from "../../format";

export const RECALC_POLL_MS = 3000;

export type Range = "1M" | "3M" | "1R" | "ALL";
export const RANGES: { value: Range; label: string }[] = [
  { value: "1M", label: "1M" }, { value: "3M", label: "3M" }, { value: "1R", label: "1R" }, { value: "ALL", label: "Wszystko" },
];
const RANGE_MONTHS: Record<Exclude<Range, "ALL">, number> = { "1M": 1, "3M": 3, "1R": 12 };

export function rangeFrom(range: Range, asOf: string | null): string | null {
  if (asOf === null || range === "ALL") return null;
  return addMonths(asOf, -RANGE_MONTHS[range]);
}

export type AllocationMode = "kind" | "account" | "currency";
export const ALLOCATION_MODES: { value: AllocationMode; label: string }[] = [
  { value: "kind", label: "Typ" }, { value: "account", label: "Konto" }, { value: "currency", label: "Waluta" },
];
export const ALLOCATION_COLORS = ["var(--alloc-1)", "var(--alloc-2)", "var(--alloc-3)", "var(--alloc-4)", "var(--alloc-5)"];

export interface AllocationRow { key: string; name: string; value: string; share: string | null; color: string }

/** Rows arrive sorted from the largest; the first gets the accent. */
export function allocationRows(mode: AllocationMode, summary: Summary, exposure: Exposure | undefined): AllocationRow[] {
  const items = mode === "kind"
    ? summary.by_kind
    : mode === "account"
      ? summary.by_account
      : (exposure?.current ?? []).map((c) => ({
        key: c.currency, name: c.currency === "unknown" ? "Nieznana" : c.currency, value_pln: c.value_pln, share_pct: c.share_pct,
      }));
  return items.map((item, i) => ({
    key: item.key, name: item.name, value: item.value_pln, share: item.share_pct,
    color: ALLOCATION_COLORS[i % ALLOCATION_COLORS.length]!,
  }));
}

/** The API gives each position's change in zł; its percent is a display-only ratio of two amounts. */
export function dayMovers(positions: Position[], count = 3): { position: Position; pct: string }[] {
  return positions
    .filter((p) => p.kind === "instrument" && toCents(p.day_change_pln) !== 0n)
    .flatMap((p) => {
      const before = Number(p.payout_pln) - Number(p.day_change_pln);
      return before > 0 ? [{ position: p, pct: ((Number(p.day_change_pln) / before) * 100).toFixed(4) }] : [];
    })
    .sort((a, b) => Math.abs(Number(b.pct)) - Math.abs(Number(a.pct)))
    .slice(0, count);
}
