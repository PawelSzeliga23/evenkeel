import type { Account, AccountUsage, Instrument } from "../../api/types";
import { pluralPl } from "../../format";

export const ACCOUNT_KIND: Record<Account["kind"], string> = {
  broker: "Rachunek maklerski", bonds: "Obligacje", savings: "Konto oszczędnościowe", cash: "Gotówka",
};
export const WRAPPER: Record<Account["wrapper"], string> = { regular: "Zwykłe", ike: "IKE", ikze: "IKZE" };
export const WRAPPER_OPTIONS = (["regular", "ike", "ikze"] as const).map((value) => ({ value, label: WRAPPER[value] }));

/** No price at all, or the last fetch failed: the position is valued from XTB figures. */
export function hasPriceProblem(instrument: Instrument): boolean {
  return instrument.price_error !== null || instrument.last_price === null;
}

export function problemsFirst(instruments: Instrument[]): Instrument[] {
  return [...instruments].sort(
    (a, b) => Number(hasPriceProblem(b)) - Number(hasPriceProblem(a)) || a.xtb_ticker.localeCompare(b.xtb_ticker),
  );
}

/** How many instruments have a price problem (the Ustawienia row's value). */
export function problemCount(instruments: Instrument[]): number {
  return instruments.filter(hasPriceProblem).length;
}

export function problemsSummary(instruments: Instrument[]): string {
  if (instruments.length === 0) return "Nie masz jeszcze instrumentów.";
  const n = instruments.filter(hasPriceProblem).length;
  if (n === 0) return "Wszystkie instrumenty mają ceny.";
  return `${n} ${pluralPl(n, "instrument wymaga", "instrumenty wymagają", "instrumentów wymaga")} uwagi.`;
}

/** "42 operacje, 3 importy" — only what there is; "" for an empty account. */
export function usageSummary(usage: AccountUsage): string {
  const parts: [number, string, string, string][] = [
    [usage.transactions, "operacja", "operacje", "operacji"],
    [usage.imports, "import", "importy", "importów"],
    [usage.bond_holdings, "zakup obligacji", "zakupy obligacji", "zakupów obligacji"],
    [usage.savings_entries, "wpis konta oszczędnościowego", "wpisy konta oszczędnościowego", "wpisów konta oszczędnościowego"],
    [usage.notes, "notatka", "notatki", "notatek"],
  ];
  return parts.filter(([n]) => n > 0).map(([n, one, few, many]) => `${n} ${pluralPl(n, one, few, many)}`).join(", ");
}
