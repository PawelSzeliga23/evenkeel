import type { Closed, ClosedInvestment, ClosedSale } from "../../api/types";

export const STATUS_LABEL: Record<ClosedInvestment["status"], string> = { closed: "sprzedane", partial: "częściowo" };

export function investmentKey(investment: ClosedInvestment): string {
  return `${investment.account_id}-${investment.instrument_id}`;
}

/** The same ticker on two accounts is two investments: match both the account and the instrument. */
export function salesOf(closed: Closed, investment: ClosedInvestment): ClosedSale[] {
  return closed.sales.filter((s) => s.account_id === investment.account_id && s.instrument_id === investment.instrument_id);
}
