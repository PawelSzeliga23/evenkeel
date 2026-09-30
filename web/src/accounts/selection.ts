/** The account filter shared by every screen: a sorted list of account ids, [] = the whole portfolio. */
import type { Account } from "../api/types";
import { pluralPl } from "../format";

export const ALL_LABEL = "Cały portfel";

const isId = (value: unknown): value is number => Number.isInteger(value) && (value as number) > 0;

/** Sorted, without repeats, only accounts that still exist; choosing every account is the same as none. */
export function normalizeSelection(ids: readonly number[], known: readonly number[] | null): number[] {
  const unique = [...new Set(ids)].filter(isId);
  const kept = known === null ? unique : unique.filter((id) => known.includes(id));
  kept.sort((a, b) => a - b);
  return known !== null && known.length > 0 && kept.length === known.length ? [] : kept;
}

/** Flip one account; from the whole portfolio (empty) that means "all except this one". */
export function toggleAccount(value: readonly number[], id: number, known: readonly number[]): number[] {
  const from = value.length === 0 ? known : value; // "whole portfolio" shows every account ticked
  const next = from.includes(id) ? from.filter((v) => v !== id) : [...from, id];
  return normalizeSelection(next, known);
}

export function selectionLabel(value: readonly number[], accounts: readonly Account[]): string {
  const chosen = accounts.filter((account) => value.includes(account.id));
  if (chosen.length === 0) return ALL_LABEL;
  if (chosen.length <= 2) return chosen.map((account) => account.name).join(", ");
  return `${chosen.length} ${pluralPl(chosen.length, "konto", "konta", "kont")}`;
}

export const storageKey = (userId: number) => `portfolio.accounts.${userId}`;

export function readSelection(userId: number): number[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(storageKey(userId)) ?? "[]");
    return Array.isArray(parsed) && parsed.every(isId) ? normalizeSelection(parsed, null) : [];
  } catch {
    return [];
  }
}

export function writeSelection(userId: number, ids: readonly number[]): void {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(ids));
  } catch {
    // private mode or full storage: the choice lives in memory only
  }
}
