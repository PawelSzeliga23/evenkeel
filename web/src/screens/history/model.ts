import type { HistoryItem } from "../../api/types";
import { shortTicker } from "../../ui/ticker";
import { transactionLabel } from "../positions/model";

const OWN_LABELS: Record<string, string> = {
  bond_purchase: "Zakup obligacji", bond_payout: "Wykup obligacji", savings_deposit: "Wpłata",
  savings_withdrawal: "Wypłata", savings_interest: "Odsetki dopisane",
};

export const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Wszystkie" },
  { value: "buy", label: "Kupno" }, { value: "sell", label: "Sprzedaż" }, { value: "dividend", label: "Dywidenda" },
  { value: "deposit", label: "Wpłata" }, { value: "withdrawal", label: "Wypłata" }, { value: "interest", label: "Odsetki" },
  { value: "fee", label: "Opłata" }, { value: "bond_purchase", label: "Zakup obligacji" },
  { value: "bond_payout", label: "Wykup obligacji" }, { value: "savings_deposit", label: "Wpłata na konto oszczędnościowe" },
  { value: "savings_withdrawal", label: "Wypłata z konta oszczędnościowego" },
  { value: "savings_interest", label: "Odsetki z konta oszczędnościowego" },
];

export function entryLabel(item: HistoryItem): string {
  return OWN_LABELS[item.type] ?? transactionLabel(item.type);
}

export function entryLead(item: HistoryItem): string {
  if (item.kind === "bond_purchase" || item.kind === "bond_payout") return "EDO";
  if (item.kind === "savings_flow" || item.kind === "savings_interest") return "%";
  return item.ticker ? shortTicker(item.ticker) : "zł";
}

export function groupByDay(items: HistoryItem[]): { date: string; items: HistoryItem[] }[] {
  const days: { date: string; items: HistoryItem[] }[] = [];
  for (const item of items) {
    const last = days.at(-1);
    if (last && last.date === item.date) last.items.push(item);
    else days.push({ date: item.date, items: [item] });
  }
  return days;
}
