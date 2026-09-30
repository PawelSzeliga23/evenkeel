import type { Account, Closed, Exposure, History, Instrument, ImportFile, ImportResult, Limit, Position, PositionDetail, Summary } from "../api/types";

export const ACCOUNTS: Account[] = [
  { id: 1, name: "IKE", kind: "broker", wrapper: "ike", broker: "xtb", external_account_number: "56216965",
    currency: "PLN", created_at: "2026-09-01T10:00:00" },
  { id: 2, name: "XTB", kind: "broker", wrapper: "regular", broker: "xtb", external_account_number: "56204082",
    currency: "PLN", created_at: "2026-09-01T10:00:00" },
];

export const SUMMARY: Summary = {
  as_of: "2026-09-26",
  value_pln: "184302.17",
  market_value_pln: "184327.67",
  exit_cost_pln: "25.50",
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
  prices_refreshed_at: "2026-09-26T20:05:00Z",
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
  const value = overrides.value_pln ?? "1000.00";
  return {
    kind: "instrument", account_id: 2, account_name: "XTB", instrument_id: 10, ticker: "SXR8.DE",
    name: "Core S&P 500", category: "ETF", currency: "EUR", quantity: "42.00000000", price: "612.3400", price_currency: "EUR",
    price_date: "2026-09-26", price_source: "provider", value_pln: value, exit_fx_pln: "0.00", exit_spread_pln: "0.00",
    exit_cost_pln: "0.00", payout_pln: value, cost_pln: "900.00",
    unrealized_pln: "100.00", unrealized_pct: "11.11", price_effect_pln: "80.00", fx_effect_pln: "20.00",
    dividends_net_pln: "0.00", fees_pln: "0.00", realized_pln: "0.00", day_change_pln: "0.00", share_pct: "10.00",
    flags: [], spread_pct: null, bond_holding_id: null, savings_account_id: null,
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

export const DETAIL: PositionDetail = {
  position: position({ instrument_id: 12, ticker: "CDR.PL", name: "CD Projekt", currency: "PLN", quantity: "48",
    price: "232.4700", price_currency: "PLN", price_source: "xtb", value_pln: "11158.56", cost_pln: "9227.52", unrealized_pln: "1931.04",
    unrealized_pct: "20.93", price_effect_pln: "1931.04", fx_effect_pln: "0.00", dividends_net_pln: "48.60",
    fees_pln: "-12.00", realized_pln: "215.30", share_pct: "6.05" }),
  lots: [
    { position_id: "777", opened_on: "2025-05-12", quantity: "30", open_price: "180.2000", cost_pln: "5406.00",
      value_pln: "6974.10", exit_cost_pln: "0.00", gain_pln: "1568.10", price_effect_pln: "1568.10", fx_effect_pln: "0.00", holding_days: 502,
      stop_loss: "150.0000", take_profit: null },
    { position_id: "778", opened_on: "2026-02-03", quantity: "18", open_price: "212.2900", cost_pln: "3821.52",
      value_pln: "4184.46", exit_cost_pln: "0.00", gain_pln: "362.94", price_effect_pln: "362.94", fx_effect_pln: "0.00", holding_days: 1,
      stop_loss: null, take_profit: null },
  ],
  sales: [
    { date: "2026-04-10", opened_on: "2025-05-12", holding_days: 333, quantity: "5", proceeds_pln: "1116.30",
      cost_pln: "901.00", realized_pln: "215.30", price_effect_pln: "215.30", fx_effect_pln: "0.00", position_id: "777", matched: true },
  ],
  income: [{ date: "2026-06-20", type: "dividend", amount: "60.00", currency: "PLN", amount_pln: "60.00" }],
  transactions: [
    { id: 1, account_id: 2, ticker: "CDR.PL", type: "buy", xtb_type: "Stock purchase", occurred_at: "2025-05-12T09:30:00",
      amount: "-5406.00", currency: "PLN", quantity: "30", price: "180.2", implied_fx_rate: null, xtb_position_id: "777",
      external_id: "1", comment: "", transfer_pair_id: null, manual: false },
  ],
  reconciliation: { status: "mismatch", taken_at: "2026-09-26T12:00:00", xtb_quantity: "50", calculated_quantity: "48" },
  average_price: "192.2338",
};

export const IMPORT_FILE: ImportFile = {
  filename: "IKE_56216965_2006-01-01_2026-09-26.xlsx", account_number: "56216965", wrapper: "ike", currency: "PLN",
  account_id: null, account_name: "IKE 56216965", new_account: true, report_from: "2006-01-01T00:00:00",
  report_to: "2026-09-26T00:00:00", new_transactions: 42, duplicate_transactions: 3, unknown_transactions: 1,
  open_lots: 5, closed_lots: 2, warnings: [{ code: "quantity_mismatch", message: "Ilość SXR8.DE różni się od XTB.", details: {} }],
  import_id: null,
};

export const PREVIEW: ImportResult = { files: [IMPORT_FILE], errors: [], skipped: [] };

export function instrument(overrides: Partial<Instrument>): Instrument {
  return {
    id: 10, xtb_ticker: "SXR8.DE", name: "Core S&P 500", category: "ETF", currency: "EUR", price_symbol: "SXR8.DE",
    price_symbol_overridden: false, price_error: null, last_price: "612.3400", last_price_date: "2026-09-26",
    spread_pct: null,
    ...overrides,
  };
}

export const BROKEN = instrument({
  id: 11, xtb_ticker: "EIMI.UK", name: "Core MSCI EM", price_symbol: "EIMI.UK", last_price: null,
  last_price_date: null, price_error: "Dostawca nie zna symbolu EIMI.UK.",
});

export const CLOSED: Closed = {
  sales: [
    { account_id: 2, account_name: "XTB", instrument_id: 13, ticker: "PKN.PL", name: "Orlen", opened_on: "2025-01-10",
      closed_on: "2026-03-05", holding_days: 419, quantity: "20", cost_pln: "1200.00", proceeds_pln: "1500.00",
      realized_pln: "300.00", price_effect_pln: "300.00", fx_effect_pln: "0.00", return_pct: "25.00", matched: true },
    { account_id: 1, account_name: "IKE", instrument_id: 13, ticker: "PKN.PL", name: "Orlen", opened_on: "2025-02-01",
      closed_on: "2026-04-01", holding_days: 424, quantity: "5", cost_pln: "300.00", proceeds_pln: "280.00",
      realized_pln: "-20.00", price_effect_pln: "-20.00", fx_effect_pln: "0.00", return_pct: "-6.67", matched: true },
  ],
  investments: [
    { account_id: 2, account_name: "XTB", instrument_id: 13, ticker: "PKN.PL", name: "Orlen", status: "closed",
      first_buy: "2025-01-10", last_sale: "2026-03-05", sold_cost_pln: "1200.00", realized_pln: "300.00",
      dividends_net_pln: "24.00", fees_pln: "-3.00", total_pln: "321.00", return_pct: "26.75" },
    { account_id: 1, account_name: "IKE", instrument_id: 13, ticker: "PKN.PL", name: "Orlen", status: "partial",
      first_buy: "2025-02-01", last_sale: "2026-04-01", sold_cost_pln: "300.00", realized_pln: "-20.00",
      dividends_net_pln: "0.00", fees_pln: "0.00", total_pln: "-20.00", return_pct: "-6.67" },
  ],
  totals: { sold_cost_pln: "1500.00", realized_pln: "280.00", dividends_net_pln: "24.00", fees_pln: "-3.00",
    total_pln: "301.00", return_pct: "20.07" },
};

export const LIMITS: Limit[] = [
  { wrapper: "ike", year: 2026, paid_pln: "12000.00", limit_pln: "28260.00", remaining_pln: "16260.00", exceeded: false,
    accounts: [{ account_id: 1, name: "IKE", paid_pln: "12000.00" }] },
  { wrapper: "ike", year: 2025, paid_pln: "26019.00", limit_pln: "26019.00", remaining_pln: "0.00", exceeded: false,
    accounts: [{ account_id: 1, name: "IKE", paid_pln: "26019.00" }] },
  { wrapper: "ikze", year: 2026, paid_pln: "12000.00", limit_pln: "11304.00", remaining_pln: "0.00", exceeded: true,
    accounts: [{ account_id: 5, name: "IKZE", paid_pln: "12000.00" }] },
  { wrapper: "ikze", year: 2022, paid_pln: "1000.00", limit_pln: null, remaining_pln: null, exceeded: false,
    accounts: [{ account_id: 5, name: "IKZE", paid_pln: "1000.00" }] },
];

export const EXPOSURE_HISTORY: Exposure = {
  as_of: "2026-09-26",
  current: [
    { currency: "EUR", value_pln: "600.00", share_pct: "60.00" },
    { currency: "PLN", value_pln: "400.00", share_pct: "40.00" },
  ],
  history: [
    { date: "2026-09-24", values: { PLN: "1000.00" } },
    { date: "2026-09-25", values: { PLN: "500.00", EUR: "500.00" } },
    { date: "2026-09-26", values: { PLN: "400.00", EUR: "600.00", USD: "-5.00" } },
  ],
};
