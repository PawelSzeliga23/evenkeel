/** Response shapes of the API (api/app/<module>/schemas.py). Decimals arrive as strings and stay strings. */
export type Money = string;
export type IsoDate = string; // "2026-09-26"
export type IsoDateTime = string; // "2026-03-02T09:30:00"

export interface TokenOut { access_token: string; token_type: string }
export interface UserOut { id: number; email: string; base_currency: string }
export interface RegisterIn { email: string; password: string; invite_code?: string }

export interface Account {
  id: number;
  name: string;
  kind: "broker" | "bonds" | "savings" | "cash";
  wrapper: "regular" | "ike" | "ikze";
  broker: string | null;
  external_account_number: string | null;
  currency: string;
  created_at: IsoDateTime;
}

export interface Allocation { key: string; name: string; value_pln: Money; share_pct: Money | null }

export interface Summary {
  as_of: IsoDate | null;
  value_pln: Money; // payout value: market value − exit costs
  market_value_pln: Money;
  exit_cost_pln: Money;
  cash_pln: Money;
  invested_pln: Money;
  total_gain_pln: Money;
  total_gain_pct: Money | null;
  day_change_pln: Money | null;
  day_change_pct: Money | null;
  twr_pct: Money | null;
  dividends_net_pln: Money;
  interest_net_pln: Money;
  fees_pln: Money;
  by_account: Allocation[];
  by_kind: Allocation[];
  approximate_positions: number;
  recalculating: boolean;
}

export interface HistoryPoint { date: IsoDate; value_pln: Money; invested_pln: Money; net_flow_pln: Money; twr_pct: Money | null }
export interface HistoryEvent { date: IsoDate; type: string; amount_pln: Money }
export interface History { points: HistoryPoint[]; events: HistoryEvent[] }

export interface ExposureItem { currency: string; value_pln: Money; share_pct: Money | null }
export interface Exposure { as_of: IsoDate | null; current: ExposureItem[]; history: { date: IsoDate; values: Record<string, Money> }[] }

export interface Position {
  kind: "instrument" | "cash" | "bond" | "savings";
  account_id: number;
  account_name: string;
  instrument_id: number | null;
  ticker: string | null;
  name: string;
  category: string | null;
  currency: string | null;
  quantity: Money;
  price: Money | null;
  price_currency: string | null;
  price_date: IsoDate | null;
  price_source: "provider" | "xtb" | null;
  value_pln: Money; // market value
  exit_fx_pln: Money; // XTB conversion fee on a sale
  exit_spread_pln: Money; // manual half-spread
  exit_cost_pln: Money;
  payout_pln: Money; // value − exit costs; gain, share and day change are from this
  cost_pln: Money;
  unrealized_pln: Money;
  unrealized_pct: Money | null;
  price_effect_pln: Money;
  fx_effect_pln: Money;
  dividends_net_pln: Money;
  fees_pln: Money;
  realized_pln: Money;
  day_change_pln: Money;
  share_pct: Money | null;
  flags: string[];
  spread_pct: Money | null;
  bond_holding_id: number | null;
  savings_account_id: number | null;
}

export interface Lot {
  position_id: string | null;
  opened_on: IsoDate;
  quantity: Money;
  open_price: Money | null;
  cost_pln: Money;
  value_pln: Money;
  exit_cost_pln: Money;
  gain_pln: Money;
  price_effect_pln: Money;
  fx_effect_pln: Money;
  holding_days: number;
  stop_loss: Money | null;
  take_profit: Money | null;
}

export interface Sale {
  date: IsoDate;
  opened_on: IsoDate;
  holding_days: number;
  quantity: Money;
  proceeds_pln: Money;
  cost_pln: Money;
  realized_pln: Money;
  price_effect_pln: Money;
  fx_effect_pln: Money;
  position_id: string | null;
  matched: boolean;
}

export interface Income { date: IsoDate; type: string; amount: Money; currency: string; amount_pln: Money }

export interface Transaction {
  id: number;
  account_id: number;
  ticker: string | null;
  type: string;
  xtb_type: string;
  occurred_at: IsoDateTime;
  amount: Money;
  currency: string;
  quantity: Money | null;
  price: Money | null;
  implied_fx_rate: Money | null;
  xtb_position_id: string | null;
  external_id: string;
  comment: string;
  transfer_pair_id: number | null;
  manual: boolean;
}

export interface Reconciliation {
  status: "ok" | "mismatch" | "no_snapshot";
  taken_at: IsoDateTime | null;
  xtb_quantity: Money | null;
  calculated_quantity: Money | null;
}

export interface PositionDetail {
  position: Position;
  lots: Lot[];
  sales: Sale[];
  income: Income[];
  transactions: Transaction[];
  reconciliation: Reconciliation;
  average_price: Money | null;
}

export interface ImportWarning { code: string; message: string; details: Record<string, unknown> }
export interface ImportFile {
  filename: string;
  account_number: string;
  wrapper: string;
  currency: string;
  account_id: number | null;
  account_name: string;
  new_account: boolean;
  report_from: IsoDateTime | null;
  report_to: IsoDateTime | null;
  new_transactions: number;
  duplicate_transactions: number;
  unknown_transactions: number;
  open_lots: number;
  closed_lots: number;
  warnings: ImportWarning[];
  import_id: number | null;
}
export interface ImportFileError { filename: string; code: string; message: string }
export interface ImportResult { files: ImportFile[]; errors: ImportFileError[]; skipped: string[] }

export interface AccountCreate { name: string; kind: Account["kind"]; wrapper?: Account["wrapper"] }
export interface AccountUpdate { name?: string; wrapper?: Account["wrapper"] }
export interface AccountUsage { transactions: number; imports: number; bond_holdings: number; savings_entries: number }

export interface Instrument {
  id: number;
  xtb_ticker: string;
  name: string;
  category: string | null;
  currency: string | null;
  price_symbol: string | null;
  price_symbol_overridden: boolean;
  price_error: string | null;
  last_price: Money | null;
  last_price_date: IsoDate | null;
  spread_pct: Money | null;
}

export type CashOperationType = "deposit" | "withdrawal" | "interest" | "fee";
export interface TransactionIn { account_id: number; type: CashOperationType; amount: Money; date: IsoDate; comment: string }

export interface BondIn {
  account_id: number;
  bond_type: "EDO";
  quantity: number;
  purchase_date: IsoDate;
  first_period_rate?: string;
  margin?: string;
}
export interface BondOut {
  id: number;
  account_id: number;
  account_name: string;
  bond_type: string;
  series: string;
  quantity: number;
  purchase_date: IsoDate;
  redeemed_at: IsoDate | null;
  maturity_date: IsoDate;
  note: string;
  status: "active" | "redeemed" | "matured";
  value_pln: Money;
  flags: string[];
}

export type Capitalization = "daily" | "monthly" | "quarterly";
export interface SavingsAccountCreate {
  name: string;
  wrapper: Account["wrapper"];
  capitalization: Capitalization;
  annual_rate: string;
  rate_valid_from: IsoDate;
  first_deposit: { date: IsoDate; amount: Money; note: string };
}
export interface SavingsFlowOut { id: number; date: IsoDate; amount: Money; note: string }
export interface SavingsSummary {
  balance: Money;
  deposits: Money;
  interest_net: Money;
  tax: Money;
  accrued: Money;
  current_rate: string | null;
}
export interface SavingsCapitalization { period_end: IsoDate; credited_on: IsoDate; gross: Money; tax: Money; net: Money }
export interface SavingsAccountOut {
  account_id: number;
  capitalization: Capitalization;
  rates: { id: number; valid_from: IsoDate; annual_rate: string }[];
  balances: { id: number; as_of_date: IsoDate; balance: Money }[];
  flows: SavingsFlowOut[];
  summary: SavingsSummary;
  capitalizations: SavingsCapitalization[];
}

export interface BondPeriod { number: number; start: IsoDate; end: IsoDate; rate: string; estimated: boolean }
export interface BondDetail {
  bond: BondOut;
  value_per_bond: Money;
  redemption_today_pln: Money | null;
  periods: BondPeriod[];
}

export type HistoryKind = "transaction" | "bond_purchase" | "bond_payout" | "savings_flow" | "savings_interest";
export interface HistoryItem {
  id: string;
  kind: HistoryKind;
  type: string;
  date: IsoDate;
  account_id: number;
  account_name: string;
  instrument_id: number | null;
  ticker: string | null;
  name: string | null;
  quantity: Money | null;
  price: Money | null;
  amount: Money;
  currency: string;
  amount_pln: Money | null;
  tax: Money | null;
  note: string;
  delete: { target: "transaction" | "bond" | "savings_flow"; id: number } | null;
}
export interface HistoryPage { items: HistoryItem[]; next_cursor: string | null }
export interface HistoryFilters { account_id: number | null; type: string | null; from: IsoDate | null; to: IsoDate | null; q: string }

export interface ClosedTotals {
  sold_cost_pln: Money;
  realized_pln: Money;
  dividends_net_pln: Money;
  fees_pln: Money;
  total_pln: Money;
  return_pct: Money | null;
}
export interface ClosedInvestment extends ClosedTotals {
  account_id: number;
  account_name: string;
  instrument_id: number;
  ticker: string;
  name: string;
  status: "closed" | "partial";
  first_buy: IsoDate;
  last_sale: IsoDate;
}
export interface ClosedSale {
  account_id: number;
  account_name: string;
  instrument_id: number;
  ticker: string;
  name: string;
  opened_on: IsoDate;
  closed_on: IsoDate;
  holding_days: number;
  quantity: Money;
  cost_pln: Money;
  proceeds_pln: Money;
  realized_pln: Money;
  price_effect_pln: Money;
  fx_effect_pln: Money;
  return_pct: Money | null;
  matched: boolean;
}
export interface Closed { sales: ClosedSale[]; investments: ClosedInvestment[]; totals: ClosedTotals }

export interface LimitAccount { account_id: number; name: string; paid_pln: Money }
export interface Limit {
  wrapper: "ike" | "ikze";
  year: number;
  paid_pln: Money;
  limit_pln: Money | null;
  remaining_pln: Money | null;
  exceeded: boolean;
  accounts: LimitAccount[];
}
