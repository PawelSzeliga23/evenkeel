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
    return items.length ? [{ key: group.key, title: group.title, total: sumMoney(items.map((p) => p.value_pln)), items }] : [];
  });
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
  return p.kind === "instrument" && p.instrument_id !== null ? `/pozycje/${p.account_id}/${p.instrument_id}` : undefined;
}

const TRANSACTION_LABELS: Record<string, string> = {
  buy: "Kupno", sell: "Sprzedaż", dividend: "Dywidenda", withholding_tax: "Podatek u źródła", interest: "Odsetki",
  interest_tax: "Podatek od odsetek", deposit: "Wpłata", withdrawal: "Wypłata", transfer_in: "Przelew przychodzący",
  transfer_out: "Przelew wychodzący", fee: "Opłata", unknown: "Nierozpoznana operacja",
};

export function transactionLabel(type: string): string {
  return TRANSACTION_LABELS[type] ?? type;
}
