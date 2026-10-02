import type { Account, Analytics, CatalogGroup, Closed, Exposure, History, Instrument, ImportFile, ImportResult, Limit, Money, Position, PositionDetail, PriceChartData, Scenario, ScenarioMeasures, ScenarioResult, Summary , Holdings, IncomeMonth, IncomeReport} from "../api/types";
import { fromCents, toCents } from "../format";

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
    flags: [], spread_pct: null, bond_holding_id: null, savings_account_id: null, tags: [],
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
  tags: [],
};

export const IMPORT_FILE: ImportFile = {
  filename: "IKE_56216965_2006-01-01_2026-09-26.xlsx", account_number: "56216965", wrapper: "ike", currency: "PLN",
  account_id: null, account_name: "IKE 56216965", new_account: true, report_from: "2006-01-01T00:00:00",
  report_to: "2026-09-26T00:00:00", new_transactions: 42, duplicate_transactions: 3, unknown_transactions: 1, reclassified_transactions: 0,
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
export const ANALYTICS: Analytics = {
  period: { start: "2026-03-01", end: "2026-09-26", days: 210, annualized: false },
  profit_pln: "804.20",
  twr: { period_pct: "8.04", annual_pct: null },
  xirr: { period_pct: "6.40", annual_pct: null },
  volatility_pct: "14.80",
  sharpe: "0.62",
  short_sample: true,
  max_drawdown: { pct: "-8.20", peak_date: "2026-08-12", trough_date: "2026-08-22", recovered_on: "2026-09-18" },
  current_drawdown_pct: "-1.30",
  best_day: { date: "2026-08-05", pct: "2.90", pln: "48.00" },
  worst_day: { date: "2026-08-14", pct: "-3.40", pln: "-57.00" },
  drawdown_series: [
    { date: "2026-08-12", pct: "0.00" }, { date: "2026-08-22", pct: "-8.20" }, { date: "2026-09-18", pct: "0.00" },
    { date: "2026-09-26", pct: "-1.30" },
  ],
  monthly: [{
    year: 2026,
    months: [null, null, "1.20", "0.50", "-0.70", "2.00", "3.10", "-3.00", "3.80", null, null, null],
    year_pct: "5.10", first_partial_month: null,
  }],
  recalculating: false,
};

export const ANALYTICS_EMPTY: Analytics = {
  period: null, profit_pln: "0.00", twr: { period_pct: null, annual_pct: null }, xirr: { period_pct: null, annual_pct: null },
  volatility_pct: null, sharpe: null, short_sample: false, max_drawdown: null, current_drawdown_pct: null,
  best_day: null, worst_day: null, drawdown_series: [], monthly: [], recalculating: false,
};

export const CATALOG: CatalogGroup[] = [
  { group: "Twój portfel", items: [{ id: 10, ticker: "SXR8.DE", name: "Core S&P 500", currency: "EUR",
    group: "Twój portfel", accumulating: true, prices_from: "2016-01-04" }] },
  { group: "ETF: USA", items: [{ id: 20, ticker: "SXRV.DE", name: "iShares NASDAQ 100", currency: "EUR",
    group: "ETF: USA", accumulating: true, prices_from: "2016-01-04" }] },
];

function measures(value: Money, xirr: Money): ScenarioMeasures {
  return {
    period: { start: "2026-03-01", end: "2026-09-26", days: 210, annualized: false },
    value_pln: value, invested_pln: "10000.00", profit_pln: fromCents(toCents(value) - 1_000_000n),
    twr: { period_pct: "8.04", annual_pct: null }, xirr: { period_pct: xirr, annual_pct: null },
    volatility_pct: "14.80", sharpe: "0.62", short_sample: true,
    max_drawdown: { pct: "-8.20", peak_date: "2026-08-12", trough_date: "2026-08-22", recovered_on: null },
    current_drawdown_pct: "-1.30", best_day: null, worst_day: null,
  };
}

/** The real portfolio ends at 10 804,20 zł with XIRR 6,40 %; the scenario at `value` with `xirr`. */
export function scenarioResult(value: Money, xirr: Money, notes: string[] = []): ScenarioResult {
  return {
    points: [
      { date: "2026-09-24", portfolio_pln: "10700.00", scenario_pln: "10900.00", invested_pln: "10000.00",
        scenario_invested_pln: "10000.00" },
      { date: "2026-09-25", portfolio_pln: "10750.00", scenario_pln: "11000.00", invested_pln: "10000.00",
        scenario_invested_pln: "10000.00" },
      { date: "2026-09-26", portfolio_pln: "10804.20", scenario_pln: value, invested_pln: "10000.00",
        scenario_invested_pln: "10000.00" },
    ],
    portfolio: measures("10804.20", "6.40"), scenario: measures(value, xirr), notes, recalculating: false,
  };
}

export function scenario(id: number, name: string, overrides: Partial<Scenario> = {}): Scenario {
  return {
    id, name, base: "portfolio", allocation: [],
    steps: [{ kind: "replace", from_instrument_id: 10, to_instrument_id: 20 }],
    created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-01T10:00:00Z", ...overrides,
  };
}

const ike = (value: string, gain: string) => [{ account_id: 1, name: "IKE", value_pln: value, gain_pln: gain }];

export const HOLDINGS: Holdings = {
  period: { start: "2026-09-25", end: "2026-09-26" },
  items: [
    { key: "i:10", kind: "instrument", ticker: "SXR8.DE", name: "Core S&P 500", category: "etf", value_pln: "1519.87",
      gain_pln: "13.49", gain_pct: "0.91", accounts: ike("1519.87", "13.49") },
    { key: "i:11", kind: "instrument", ticker: "VIE.FR", name: "Veolia", category: "stock", value_pln: "193.00",
      gain_pln: "2.31", gain_pct: "1.20", accounts: [{ account_id: 2, name: "XTB", value_pln: "193.00", gain_pln: "2.31" }] },
    { key: "s:5", kind: "savings", ticker: null, name: "Trade Republic", category: "savings", value_pln: "10047.00",
      gain_pln: "1.32", gain_pct: "0.01", accounts: [{ account_id: 5, name: "Trade Republic", value_pln: "10047.00", gain_pln: "1.32" }] },
    { key: "b:EDO0935", kind: "bond", ticker: null, name: "EDO0935", category: "bonds", value_pln: "1500.00",
      gain_pln: "0.30", gain_pct: "0.02", accounts: [{ account_id: 6, name: "Obligacje", value_pln: "1500.00", gain_pln: "0.30" }] },
    { key: "i:12", kind: "instrument", ticker: "SNT.PL", name: "Synektik", category: "stock", value_pln: "100.00",
      gain_pln: "-1.83", gain_pct: "-1.80", accounts: ike("100.00", "-1.83") },
  ],
  by_account: [
    { key: "1", name: "IKE", value_pln: "1619.87", gain_pln: "11.66", gain_pct: "0.72" },
    { key: "5", name: "Trade Republic", value_pln: "10047.00", gain_pln: "1.32", gain_pct: "0.01" },
  ],
  by_kind: [
    { key: "etf", name: "ETF", value_pln: "1519.87", gain_pln: "13.49", gain_pct: "0.91" },
    { key: "savings", name: "Oszczędności", value_pln: "10047.00", gain_pln: "1.32", gain_pct: "0.01" },
  ],
  recalculating: false,
};

export const HOLDINGS_EMPTY: Holdings = { period: null, items: [], by_account: [], by_kind: [], recalculating: false };

const incomeMonth = (month: string, interest: string, fx: string, taxes = "0.00"): IncomeMonth => {
  const costs = (Number(fx) + Number(taxes)).toFixed(2);
  return { month, interest_pln: interest, dividends_pln: "0.00", fx_pln: fx, taxes_pln: taxes, fees_pln: "0.00",
    income_pln: interest, costs_pln: costs, balance_pln: (Number(interest) - Number(costs)).toFixed(2) };
};

export const INCOME: IncomeReport = {
  period: { start: "2026-08-01", end: "2026-10-02" },
  totals: { income_pln: "82.34", costs_pln: "69.10", balance_pln: "13.24" },
  months: [incomeMonth("2026-08", "4.40", "14.50"), incomeMonth("2026-09", "74.84", "38.66", "11.04"),
    incomeMonth("2026-10", "3.10", "4.90")],
  sources: [
    { key: "s:5", kind: "savings", name: "Trade Republic", gross_pln: "58.10", tax_pln: "11.04", net_pln: "47.06", taxed: true },
    { key: "b:EDO0935", kind: "bond", name: "EDO0935", gross_pln: "24.24", tax_pln: "0.00", net_pln: "24.24", taxed: false },
  ],
  costs: [
    { key: "fx", name: "Przewalutowanie XTB", amount_pln: "58.06", count: 12 },
    { key: "interest_tax", name: "Podatek od odsetek", amount_pln: "11.04", count: 0 },
    { key: "withholding_tax", name: "Podatek u źródła", amount_pln: "0.00", count: 0 },
    { key: "fees", name: "Prowizje i opłaty", amount_pln: "0.00", count: 0 },
  ],
  recalculating: false,
};

export const INCOME_EMPTY: IncomeReport = {
  period: null, totals: { income_pln: "0.00", costs_pln: "0.00", balance_pln: "0.00" }, months: [], sources: [],
  costs: [], recalculating: false,
};

/** CD Projekt closes once a week from 01.04.2025, 232,47 zł at the end, with the position's operations. */
export const PRICE_CHART: PriceChartData = {
  currency: "PLN",
  points: Array.from({ length: 78 }, (_, i) => ({
    date: new Date(Date.UTC(2025, 3, 1 + 7 * i)).toISOString().slice(0, 10),
    close: i === 77 ? "232.47" : (170 + i * 0.8).toFixed(2),
  })),
  markers: [
    { date: "2025-05-12", kind: "buy", price: "180.2", price_with_fx: null, quantity: "30", amount_pln: "-5406.00" },
    { date: "2026-02-03", kind: "buy", price: "212.29", price_with_fx: null, quantity: "18", amount_pln: "-3821.52" },
    { date: "2026-04-10", kind: "sell", price: "223.26", price_with_fx: null, quantity: "5", amount_pln: "1116.30" },
    { date: "2026-06-20", kind: "dividend", price: null, price_with_fx: null, quantity: null, amount_pln: "60.00" },
  ],
  first_buy: "2025-05-12",
};
