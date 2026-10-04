/** Response shapes of the API (api/app/<module>/schemas.py). Decimals arrive as strings and stay strings. */
export type Money = string;
export type IsoDate = string; // "2026-09-26"
export type IsoDateTime = string; // "2026-03-02T09:30:00"

export interface TokenOut { access_token: string; token_type: string }
export interface UserOut { id: number; email: string; base_currency: string; preferences?: Partial<Preferences> }
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
  /** When the prices of the user's instruments were last checked; null without instruments. */
  prices_refreshed_at: string | null;
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
  tags: TagOn[];
}

export interface Lot {
  position_id: string | null;
  opened_on: IsoDate;
  quantity: Money;
  open_price: Money | null; // XTB's own purchase price, as XTB shows it
  open_price_with_fx?: Money | null; // with XTB's conversion (foreign instruments only)
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
  tags: TagOn[];
  notes: HoldingNotes;
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
  reclassified_transactions: number;
  open_lots: number;
  closed_lots: number;
  warnings: ImportWarning[];
  import_id: number | null;
}
export interface ImportFileError { filename: string; code: string; message: string }
export interface ImportResult { files: ImportFile[]; errors: ImportFileError[]; skipped: string[] }

export interface AccountCreate { name: string; kind: Account["kind"]; wrapper?: Account["wrapper"] }
export interface AccountUpdate { name?: string; wrapper?: Account["wrapper"] }
export interface AccountUsage {
  transactions: number; imports: number; bond_holdings: number; savings_entries: number; notes: number;
}

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
export interface InstrumentUpdate { price_symbol?: string | null; spread_pct?: string | null }

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
  tags: TagOn[];
  notes: HoldingNotes;
}

export interface BondPeriod { number: number; start: IsoDate; end: IsoDate; rate: string; estimated: boolean }
export interface BondDetail {
  bond: BondOut;
  value_per_bond: Money;
  redemption_today_pln: Money | null;
  periods: BondPeriod[];
  tags: TagOn[];
  notes: HoldingNotes;
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
  price_currency: string | null;
  amount: Money;
  currency: string;
  amount_pln: Money | null;
  tax: Money | null;
  note: string;
  delete: { target: "transaction" | "bond" | "savings_flow"; id: number } | null;
}
export interface HistoryPage { items: HistoryItem[]; next_cursor: string | null }
export interface HistoryFilters { account_ids: number[]; type: string | null; from: IsoDate | null; to: IsoDate | null; q: string }

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
export type AnalyticsPeriod = "1m" | "3m" | "1y" | "ytd" | "all";
export interface PeriodReturn { period_pct: Money | null; annual_pct: Money | null }
export interface DayExtreme { date: IsoDate; pct: Money; pln: Money }
export interface MonthReturns { year: number; months: (Money | null)[]; year_pct: Money | null; first_partial_month: number | null }
export interface Analytics {
  period: { start: IsoDate; end: IsoDate; days: number; annualized: boolean } | null;
  profit_pln: Money;
  twr: PeriodReturn;
  xirr: PeriodReturn;
  volatility_pct: Money | null;
  sharpe: Money | null;
  short_sample: boolean;
  max_drawdown: { pct: Money; peak_date: IsoDate; trough_date: IsoDate; recovered_on: IsoDate | null } | null;
  current_drawdown_pct: Money | null;
  best_day: DayExtreme | null;
  worst_day: DayExtreme | null;
  drawdown_series: { date: IsoDate; pct: Money }[];
  monthly: MonthReturns[];
  recalculating: boolean;
}

export interface CatalogItem {
  id: number; ticker: string; name: string; currency: string | null; group: string; accumulating: boolean | null;
  prices_from: IsoDate | null;
}
export interface CatalogGroup { group: string; items: CatalogItem[] }

export type ScenarioBase = "portfolio" | "deposits";
export interface ScenarioTarget { instrument_id: number | null; bond: "EDO" | null }
export interface ScenarioShare { target: ScenarioTarget; share_pct: Money }
export interface ReplaceStep { kind: "replace"; from_instrument_id: number; to_instrument_id: number }
export interface RecurringStep {
  kind: "recurring"; amount_pln: Money; day_of_month: number; start: string; end: string | null; target: ScenarioTarget;
  ike: boolean;
}
export type ScenarioStep = ReplaceStep | RecurringStep;
export interface ScenarioIn { name: string; base: ScenarioBase; allocation: ScenarioShare[]; steps: ScenarioStep[] }
export interface Scenario extends ScenarioIn { id: number; created_at: IsoDateTime; updated_at: IsoDateTime }
export interface ScenarioPoint {
  date: IsoDate; portfolio_pln: Money | null; scenario_pln: Money | null; invested_pln: Money | null;
  scenario_invested_pln: Money | null;
}
export interface ScenarioMeasures {
  period: { start: IsoDate; end: IsoDate; days: number; annualized: boolean };
  value_pln: Money;
  invested_pln: Money;
  profit_pln: Money;
  twr: PeriodReturn;
  xirr: PeriodReturn;
  volatility_pct: Money | null;
  sharpe: Money | null;
  short_sample: boolean;
  max_drawdown: Analytics["max_drawdown"];
  current_drawdown_pct: Money | null;
  best_day: DayExtreme | null;
  worst_day: DayExtreme | null;
}
export interface ScenarioResult {
  points: ScenarioPoint[]; portfolio: ScenarioMeasures | null; scenario: ScenarioMeasures | null; notes: string[];
  recalculating: boolean;
}

export interface ReviewListItem {
  id: number; created_at: IsoDateTime; account_label: string; sections: number; summary: string | null;
}
export interface Review extends ReviewListItem { content: string }

export type HoldingsPeriod = "1d" | "1w" | "1m" | "1y" | "ytd" | "all";

export interface Holding {
  key: string; // i:{instrument id} | b:{bond series} | s:{savings account id}
  kind: "instrument" | "bond" | "savings";
  ticker: string | null;
  name: string;
  category: "etf" | "stock" | "other" | "bonds" | "savings";
  value_pln: Money;
  gain_pln: Money;
  gain_pct: Money | null;
  accounts: { account_id: number; name: string; value_pln: Money; gain_pln: Money }[];
}

export interface GroupGain {
  key: string;
  name: string;
  value_pln: Money;
  gain_pln: Money;
  gain_pct: Money | null;
}

export interface Holdings {
  period: { start: IsoDate; end: IsoDate } | null;
  items: Holding[];
  by_account: GroupGain[];
  by_kind: GroupGain[];
  recalculating: boolean;
}

export type IncomePeriod = "12m" | "ytd" | "all";

export interface IncomeTotals { income_pln: Money; costs_pln: Money; balance_pln: Money }

export interface IncomeMonth extends IncomeTotals {
  month: string; // "2026-09"
  interest_pln: Money;
  dividends_pln: Money;
  fx_pln: Money;
  taxes_pln: Money;
  fees_pln: Money;
}

export interface IncomeSource {
  key: string;
  kind: "savings" | "bond" | "xtb_interest" | "dividend";
  name: string;
  gross_pln: Money;
  tax_pln: Money;
  net_pln: Money;
  taxed: boolean;
}

export interface IncomeCost { key: "fx" | "interest_tax" | "withholding_tax" | "fees"; name: string; amount_pln: Money; count: number }

export interface IncomeReport {
  period: { start: IsoDate; end: IsoDate } | null;
  totals: IncomeTotals;
  months: IncomeMonth[];
  sources: IncomeSource[];
  costs: IncomeCost[];
  recalculating: boolean;
}

export interface PricePoint { date: IsoDate; close: Money }
/** price and quantity after later splits; a dividend has neither. price_with_fx only for a foreign instrument. */
export interface PriceMarker {
  date: IsoDate;
  kind: "buy" | "sell" | "dividend";
  price: Money | null;
  price_with_fx: Money | null;
  quantity: Money | null;
  amount_pln: Money | null; // null while the NBP rate of its day is still missing
}
export interface PriceChartData {
  currency: string | null;
  points: PricePoint[];
  markers: PriceMarker[];
  notes: PriceNote[];
  first_buy: IsoDate | null;
}

/** The owner's tag (plan 7f-1); `links` = how many holdings it is on. */
export interface Tag { id: number; name: string; color: string; links: number }
/** A tag as it shows on a holding: `own` = only on this account. */
export interface TagOn { id: number; name: string; color: string; link_id: number; own: boolean }
/** A link target: a holding (with `account_id` only on that account), or a savings account by `account_id` alone. */
export interface TagLinkIn { instrument_id?: number; bond_series?: string; account_id?: number }

export interface TagRow {
  id: number; name: string; color: string; value_pln: Money; share_pct: string | null; gain_pln: Money;
  gain_pct: string | null; holdings: number;
}
export interface TagsReport {
  period: { start: IsoDate; end: IsoDate } | null;
  total_pln: Money;
  tags: TagRow[];
  untagged: { value_pln: Money; share_pct: string | null; gain_pln: Money; gain_pct: string | null; holdings: number } | null;
  cash: { value_pln: Money; share_pct: string | null };
  history: { dates: IsoDate[]; series: { key: string; share_pct: string[] }[] };
  recalculating: boolean;
}

/** Notes (plan 7f-2): an entry as the holding's details show it. */
export interface NoteEntry { id: number; entry_date: IsoDate; body: string; created_at: string; updated_at: string }
export interface HoldingNotes { thesis: { body: string; updated_at: string } | null; recent: NoteEntry[]; count: number }
export interface TargetLink {
  kind: "position" | "bond" | "savings";
  account_id: number | null;
  instrument_id: number | null;
  bond_holding_id: number | null;
}
/** A holding a note can be about; `key` is i:{instrument}, b:{series} or s:{savings account}. */
export interface NoteHolding { key: string; label: string; sublabel: string | null; closed: boolean; link: TargetLink | null }
export interface JournalEntry extends NoteEntry { target: NoteHolding | null }
export interface Journal { entries: JournalEntry[]; count: number }
export interface NoteTargetIn { instrument_id?: number; bond_series?: string; account_id?: number }
export interface EntryIn extends NoteTargetIn { entry_date?: IsoDate; body: string }
export interface EntryPatch extends NoteTargetIn { entry_date?: IsoDate; body?: string; portfolio?: boolean }
export interface PriceNote { date: IsoDate; entries: { id: number; entry_date: IsoDate; body: string }[] }

/** Plan 8a: the owner's start screen and default views (stored on the server). */
export type StartScreen = "dashboard" | "positions" | "history" | "analysis";
export type AccountsStart = "last" | "all" | "fixed";
export interface Preferences {
  start_screen: StartScreen;
  accounts_start: AccountsStart;
  accounts_fixed: number[];
  analysis_period: AnalyticsPeriod;
  holdings_period: HoldingsPeriod;
  value_range: "1M" | "3M" | "1R" | "ALL";
  price_range: "buy" | "6m" | "1y" | "5y" | "max";
  holdings_without_fixed_income: boolean;
}

/** Plan 8c: what a backup file holds (POST /api/backup/check and /restore). */
export interface BackupSummary {
  exported_at: string;
  app_version: string;
  counts: {
    accounts: number; transactions: number; bond_holdings: number; savings_accounts: number;
    tags: number; notes: number; scenarios: number; ai_reviews: number;
  };
}

/** Plan 8c: GET /api/market/schedule — the worker's refresh schedule and the user's last refresh. */
export interface RefreshSchedule {
  intraday_every_minutes: number;
  intraday_from: string;
  intraday_to: string;
  daily_at: string;
  timezone: string;
  last_refreshed_at: string | null;
}

/** Plan 8d: one signed-in device (GET /api/auth/sessions). */
export interface SessionInfo {
  id: string;
  user_agent: string | null;
  started_at: string;
  last_used_at: string;
  current: boolean;
}
