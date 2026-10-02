import type { TagLinkIn, TagOn } from "../api/types";

/** The tag colours, in the order new tags take them (the API's palette). */
export const TAG_PALETTE = ["#F0A43A", "#7FB6E6", "#5DB98A", "#C98BD9", "#E0C36A", "#E0676E", "#6FC7C0", "#B0B7C3"] as const;

/** What a tag goes on: an instrument or a bond series (on every account, or only this one), or a savings account. */
export type TagTarget = { instrument_id: number } | { bond_series: string } | { savings: true };
export type TagLevel = "everywhere" | "own";

export function linkBody(target: TagTarget, level: TagLevel, accountId: number): TagLinkIn {
  if ("savings" in target) return { account_id: accountId };
  return level === "own" ? { ...target, account_id: accountId } : { ...target };
}

export function rows(tags: TagOn[]): { everywhere: TagOn[]; own: TagOn[] } {
  return { everywhere: tags.filter((t) => !t.own), own: tags.filter((t) => t.own) };
}
