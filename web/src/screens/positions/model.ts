import type { Position } from "../../api/types";
import { formatDecimal, formatPercent, sumMoney } from "../../format";
import { shortTicker } from "../../ui/ticker";

const GROUPS = [
  { key: "instruments", title: "Akcje i ETF-y", kinds: ["instrument"] },
  { key: "bonds", title: "Obligacje", kinds: ["bond"] },
  { key: "accounts", title: "Konta i gotówka", kinds: ["savings", "cash"] },
] as const;

export interface PositionGroup { key: (typeof GROUPS)[number]["key"]; title: string; total: string; items: Position[] }

export function groupPositions(positions: Position[]): PositionGroup[] {
  return GROUPS.flatMap((group) => {
    const items = positions.filter((p) => (group.kinds as readonly string[]).includes(p.kind));
    return items.length ? [{ key: group.key, title: group.title, total: sumMoney(items.map((p) => p.payout_pln)), items }] : [];
  });
}

export interface TagGroup { key: string; title: string; color: string | null; total: string; items: Position[] }

/** Pozycje by tag: a holding sits in each of its tags' groups (largest group first), then „bez tagu”, then cash. */
export function groupByTag(positions: Position[]): TagGroup[] {
  const byTag = new Map<number, TagGroup>();
  const untagged: Position[] = [];
  const cash: Position[] = [];
  for (const p of positions) {
    if (p.kind === "cash") cash.push(p);
    else if (p.tags.length === 0) untagged.push(p);
    for (const tag of p.kind === "cash" ? [] : p.tags) {
      const group = byTag.get(tag.id) ?? { key: `tag-${tag.id}`, title: tag.name, color: tag.color, total: "0", items: [] };
      if (!group.items.includes(p)) group.items.push(p);
      byTag.set(tag.id, group);
    }
  }
  const total = (items: Position[]) => sumMoney(items.map((p) => p.payout_pln));
  const tagged = [...byTag.values()].map((g) => ({ ...g, total: total(g.items) }))
    .sort((a, b) => Number(b.total) - Number(a.total) || a.title.localeCompare(b.title, "pl"));
  const rest: TagGroup[] = [
    { key: "untagged", title: "bez tagu", color: null, total: total(untagged), items: untagged },
    { key: "cash", title: "Gotówka", color: null, total: total(cash), items: cash },
  ];
  return [...tagged, ...rest.filter((g) => g.items.length > 0)];
}

const FLAG_LABELS: Record<string, string> = {
  xtb_price: "cena z XTB",
  fx_missing: "brak kursu waluty",
  rate_estimated: "stopa szacunkowa",
};

export function flagLabel(flag: string): string {
  return FLAG_LABELS[flag] ?? "wycena przybliżona";
}

export function leadFor(p: Position): string {
  if (p.kind === "bond") return "EDO";
  if (p.kind === "savings") return "%";
  if (p.kind === "cash") return "zł";
  return shortTicker(p.ticker ?? p.name);
}

export function subtitleFor(p: Position): string {
  const quantity = `${formatDecimal(p.quantity, 8)} szt.`;
  if (p.kind === "instrument") {
    const share = p.share_pct === null ? "" : `, udział ${formatPercent(p.share_pct, { sign: false, places: 1 })}`;
    return `${p.account_name}, ${quantity}${share}`;
  }
  if (p.kind === "bond") return `${p.account_name}, ${quantity}`;
  if (p.kind === "savings") return p.account_name;
  return `${p.account_name}, ${p.currency ?? "PLN"}`;
}

export function positionLink(p: Position): string | undefined {
  if (p.kind === "instrument" && p.instrument_id !== null) return `/pozycje/${p.account_id}/${p.instrument_id}`;
  if (p.kind === "bond" && p.bond_holding_id !== null) return `/pozycje/obligacje/${p.bond_holding_id}`;
  if (p.kind === "savings") return `/pozycje/oszczednosci/${p.account_id}`;
  return undefined;
}

const TRANSACTION_LABELS: Record<string, string> = {
  buy: "Kupno", sell: "Sprzedaż", dividend: "Dywidenda", withholding_tax: "Podatek u źródła", interest: "Odsetki",
  interest_tax: "Podatek od odsetek", deposit: "Wpłata", withdrawal: "Wypłata", transfer_in: "Przelew przychodzący",
  transfer_out: "Przelew wychodzący", fee: "Opłata", unknown: "Nierozpoznana operacja",
};

export function transactionLabel(type: string): string {
  return TRANSACTION_LABELS[type] ?? type;
}
