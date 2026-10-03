import type { EntryPatch, JournalEntry, NoteHolding, NoteTargetIn, TargetLink } from "../api/types";
import { monthLong } from "../format";

export const MAX_THESIS = 5000;
export const MAX_ENTRY = 2000;
export const RECENT = 3;
/** The value of „Portfel” wherever a holding is chosen. */
export const PORTFOLIO = "portfolio";
export const NO_ENTRIES = "Zapisuj, dlaczego kupujesz i sprzedajesz.";

/** The holding a note is about: an instrument, a bond series or a savings account (its account id). */
export type NoteTarget = { instrument_id: number } | { bond_series: string } | { account_id: number };

export function targetKey(target: NoteTarget): string {
  if ("instrument_id" in target) return `i:${target.instrument_id}`;
  if ("bond_series" in target) return `b:${target.bond_series}`;
  return `s:${target.account_id}`;
}

/** The API's holding fields of a key; the portfolio has none. */
export function targetBody(key: string): NoteTargetIn {
  const value = key.slice(2);
  if (key.startsWith("i:")) return { instrument_id: Number(value) };
  if (key.startsWith("b:")) return { bond_series: value };
  if (key.startsWith("s:")) return { account_id: Number(value) };
  return {};
}

/** What a PATCH sends to move an entry to `key`. */
export function moveBody(key: string): EntryPatch {
  return key === PORTFOLIO ? { portfolio: true } : targetBody(key);
}

export function linkPath(link: TargetLink | null): string | null {
  if (link === null) return null;
  if (link.kind === "bond") return link.bond_holding_id === null ? null : `/pozycje/obligacje/${link.bond_holding_id}`;
  if (link.kind === "savings") return link.account_id === null ? null : `/pozycje/oszczednosci/${link.account_id}`;
  return link.account_id === null || link.instrument_id === null ? null : `/pozycje/${link.account_id}/${link.instrument_id}`;
}

/** The entries (newest first) in month groups: „październik 2026”. */
export function byMonth(entries: JournalEntry[]): { month: string; entries: JournalEntry[] }[] {
  const groups: { month: string; entries: JournalEntry[] }[] = [];
  for (const entry of entries) {
    const month = monthLong(entry.entry_date);
    const last = groups[groups.length - 1];
    if (last && last.month === month) last.entries.push(entry);
    else groups.push({ month, entries: [entry] });
  }
  return groups;
}

export function choiceLabel(holding: NoteHolding): string {
  const sub = holding.sublabel && holding.sublabel !== holding.label ? ` · ${holding.sublabel}` : "";
  return `${holding.label}${sub}${holding.closed ? " (zamknięty)" : ""}`;
}
