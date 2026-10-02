import type { IncomeMonth, IncomePeriod } from "../../api/types";
import { MONTHS } from "../analysis/model";

export const PERIODS: { value: IncomePeriod; label: string }[] = [
  { value: "12m", label: "12 mies." }, { value: "ytd", label: "Od pocz. roku" }, { value: "all", label: "Wszystko" },
];

export interface Bucket {
  key: string; label: string; title: string;
  interest: number; dividends: number; fx: number; taxes: number; fees: number;
  income: number; costs: number; balance: number;
}

const YEARS_FROM = 24;

function fromMonth(m: IncomeMonth): Bucket {
  const [year, month] = m.month.split("-");
  const name = MONTHS[Number(month) - 1]!;
  return {
    key: m.month, label: name, title: `${name} ${year}`,
    interest: Number(m.interest_pln), dividends: Number(m.dividends_pln), fx: Number(m.fx_pln),
    taxes: Number(m.taxes_pln), fees: Number(m.fees_pln), income: Number(m.income_pln), costs: Number(m.costs_pln),
    balance: Number(m.balance_pln),
  };
}

/** Months as chart buckets; years once there are more than 24 months (the bars would be too thin). */
export function buckets(months: IncomeMonth[]): Bucket[] {
  const all = months.map(fromMonth);
  if (all.length <= YEARS_FROM) return all;
  const years = new Map<string, Bucket>();
  for (const b of all) {
    const year = b.key.slice(0, 4);
    const sum = years.get(year) ?? { ...b, key: year, label: year, title: year, interest: 0, dividends: 0, fx: 0, taxes: 0, fees: 0, income: 0, costs: 0, balance: 0 };
    for (const field of ["interest", "dividends", "fx", "taxes", "fees", "income", "costs", "balance"] as const) sum[field] += b[field];
    years.set(year, sum);
  }
  return [...years.values()];
}
