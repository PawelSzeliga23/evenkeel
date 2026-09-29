import type { Account, Exposure, History, Position, Summary } from "../api/types";

export const ACCOUNTS: Account[] = [
  { id: 1, name: "IKE", kind: "broker", wrapper: "ike", broker: "xtb", external_account_number: "56216965",
    currency: "PLN", created_at: "2026-09-01T10:00:00" },
  { id: 2, name: "XTB", kind: "broker", wrapper: "regular", broker: "xtb", external_account_number: "56204082",
    currency: "PLN", created_at: "2026-09-01T10:00:00" },
];

export const SUMMARY: Summary = {
  as_of: "2026-09-26",
  value_pln: "184302.17",
  cash_pln: "4133.49",
  invested_pln: "161183.77",
  total_gain_pln: "23118.40",
  total_gain_pct: "14.34",
  day_change_pln: "1204.50",
  day_change_pct: "0.66",
  twr_pct: "14.20",
  dividends_net_pln: "3212.05",
  interest_net_pln: "200.00",
  fees_pln: "-45.10",
  by_account: [
    { key: "1", name: "IKE", value_pln: "120000.00", share_pct: "65.11" },
    { key: "2", name: "XTB", value_pln: "64302.17", share_pct: "34.89" },
  ],
  by_kind: [
    { key: "ETF", name: "ETF", value_pln: "119556.50", share_pct: "64.87" },
    { key: "savings", name: "Konta oszczędnościowe", value_pln: "40132.18", share_pct: "21.78" },
    { key: "bonds", name: "Obligacje", value_pln: "20480.00", share_pct: "11.11" },
    { key: "cash", name: "Gotówka", value_pln: "4133.49", share_pct: "2.24" },
  ],
  approximate_positions: 1,
  recalculating: false,
};

export const HISTORY: History = {
  points: [
    { date: "2026-09-24", value_pln: "182000.00", invested_pln: "161183.77", net_flow_pln: "0.00", twr_pct: "13.10" },
    { date: "2026-09-25", value_pln: "183097.67", invested_pln: "161183.77", net_flow_pln: "0.00", twr_pct: "13.60" },
    { date: "2026-09-26", value_pln: "184302.17", invested_pln: "161183.77", net_flow_pln: "0.00", twr_pct: "14.20" },
  ],
  events: [],
};

export const EXPOSURE: Exposure = {
  as_of: "2026-09-26",
  current: [
    { currency: "EUR", value_pln: "98000.00", share_pct: "53.17" },
    { currency: "PLN", value_pln: "86302.17", share_pct: "46.83" },
  ],
  history: [],
};

export function position(overrides: Partial<Position>): Position {
  return {
    kind: "instrument", account_id: 2, account_name: "XTB", instrument_id: 10, ticker: "SXR8.DE",
    name: "Core S&P 500", category: "ETF", currency: "EUR", quantity: "42.00000000", price: "612.3400",
    price_date: "2026-09-26", price_source: "provider", value_pln: "1000.00", cost_pln: "900.00",
    unrealized_pln: "100.00", unrealized_pct: "11.11", price_effect_pln: "80.00", fx_effect_pln: "20.00",
    dividends_net_pln: "0.00", fees_pln: "0.00", realized_pln: "0.00", day_change_pln: "0.00", share_pct: "10.00",
    flags: [], bond_holding_id: null, savings_account_id: null,
    ...overrides,
  };
}

export const POSITIONS: Position[] = [
  position({ instrument_id: 10, account_id: 1, account_name: "IKE", value_pln: "66024.73", day_change_pln: "688.14",
    unrealized_pln: "10354.51", share_pct: "35.82" }),
  position({ instrument_id: 11, ticker: "IWDA.NL", name: "Core MSCI World", value_pln: "31518.90", share_pct: "17.10" }),
  position({ instrument_id: 12, ticker: "CDR.PL", name: "CD Projekt", currency: "PLN", quantity: "48",
    value_pln: "11158.56", day_change_pln: "412.80", unrealized_pln: "1931.04", share_pct: "6.05" }),
  position({ instrument_id: 13, ticker: "PKN.PL", name: "Orlen", currency: "PLN", quantity: "110",
    value_pln: "7146.70", day_change_pln: "-151.20", unrealized_pln: "-612.50", share_pct: "3.88", flags: ["xtb_price"] }),
  position({ kind: "bond", instrument_id: null, ticker: null, name: "EDO0936", category: "bonds", currency: "PLN",
    account_id: 3, account_name: "Obligacje", quantity: "100", value_pln: "10013.00", cost_pln: "10000.00",
    unrealized_pln: "13.00", bond_holding_id: 7, share_pct: "5.43" }),
  position({ kind: "savings", instrument_id: null, ticker: null, name: "Konto oszczędnościowe", category: "savings",
    currency: "PLN", account_id: 4, account_name: "Konto oszczędnościowe", quantity: "40132.18",
    value_pln: "40132.18", cost_pln: "40000.00", unrealized_pln: "132.18", savings_account_id: 4, share_pct: "21.78" }),
  position({ kind: "cash", instrument_id: null, ticker: null, name: "Gotówka", category: null, currency: "PLN",
    account_id: 2, account_name: "XTB", quantity: "4133.49", value_pln: "4133.49", cost_pln: "4133.49",
    unrealized_pln: "0.00", share_pct: "2.24" }),
];
