import type { TagLinkIn, TagOn } from "../api/types";

/** The tag colours, in the order new tags take them: the values the API stores and accepts, not colours to paint.
 * Paint a tag with tagColor(), which gives the theme's --tag-N from chart-colors.css. */
export const TAG_PALETTE = ["#F0A43A", "#7FB6E6", "#5DB98A", "#C98BD9", "#E0C36A", "#E0676E", "#6FC7C0", "#B0B7C3"] as const; // colour-guard: allow

/** The colour to paint a tag with: its palette slot in the current theme, or the stored value if it is not a palette colour. */
export function tagColor(stored: string): string {
  const slot = TAG_PALETTE.findIndex((hex) => hex.toLowerCase() === stored.toLowerCase());
  return slot === -1 ? stored : `var(--tag-${slot + 1})`;
}

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
