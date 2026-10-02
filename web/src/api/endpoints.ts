import { request } from "./client";
import type {
  Account, AccountCreate, Analytics, AnalyticsPeriod, Holdings, HoldingsPeriod, IncomePeriod, IncomeReport, AccountUpdate, AccountUsage, CatalogGroup, CatalogItem, Review, ReviewListItem, Instrument, InstrumentUpdate, Scenario, ScenarioIn, ScenarioResult, BondDetail, BondIn, BondOut, Closed, Exposure, History, HistoryFilters, HistoryPage, ImportResult, IsoDate, Limit, Position, PositionDetail, PriceChartData, RegisterIn, SavingsAccountCreate, SavingsAccountOut, SavingsFlowOut, Summary, TokenOut, Transaction, TransactionIn, UserOut,
} from "./types";

function filesForm(files: File[]): FormData {
  const form = new FormData();
  for (const file of files) form.append("files", file, file.name);
  return form;
}

export const api = {
  bond: (id: number) => request<BondDetail>(`/api/bonds/${id}`),
  redeemBond: (id: number, redeemedAt: IsoDate | null) =>
    request<BondOut>(`/api/bonds/${id}`, { method: "PATCH", json: { redeemed_at: redeemedAt } }),
  deleteBond: (id: number) => request<void>(`/api/bonds/${id}`, { method: "DELETE" }),
  savings: (accountId: number) => request<SavingsAccountOut>(`/api/savings-accounts/${accountId}`),
  addSavingsFlow: (accountId: number, body: { date: IsoDate; amount: string; note: string }) =>
    request<SavingsFlowOut>(`/api/savings-accounts/${accountId}/flows`, { method: "POST", json: body }),
  deleteSavingsFlow: (accountId: number, id: number) =>
    request<void>(`/api/savings-accounts/${accountId}/flows/${id}`, { method: "DELETE" }),
  addSavingsRate: (accountId: number, body: { valid_from: IsoDate; annual_rate: string }) =>
    request<unknown>(`/api/savings-accounts/${accountId}/rates`, { method: "POST", json: body }),
  deleteTransaction: (id: number) => request<void>(`/api/transactions/${id}`, { method: "DELETE" }),
  entries: (filters: HistoryFilters, cursor: string | null) =>
    request<HistoryPage>("/api/history", {
      query: { account_id: filters.account_ids, type: filters.type, from: filters.from, to: filters.to, q: filters.q, cursor },
    }),
  login: (email: string, password: string) =>
    request<TokenOut>("/api/auth/login", { method: "POST", json: { email, password }, auth: false }),
  register: (body: RegisterIn) => request<UserOut>("/api/auth/register", { method: "POST", json: body, auth: false }),
  logout: () => request<void>("/api/auth/logout", { method: "POST", auth: false }),
  me: () => request<UserOut>("/api/auth/me"),
  accounts: () => request<Account[]>("/api/accounts"),
  changePassword: (current: string, next: string) =>
    request<void>("/api/auth/password", { method: "POST", json: { current_password: current, new_password: next } }),
  updateAccount: (id: number, body: AccountUpdate) => request<Account>(`/api/accounts/${id}`, { method: "PATCH", json: body }),
  deleteAccount: (id: number) => request<void>(`/api/accounts/${id}`, { method: "DELETE" }),
  accountUsage: (id: number) => request<AccountUsage>(`/api/accounts/${id}/usage`),
  instruments: () => request<Instrument[]>("/api/instruments"),
  updateInstrument: (id: number, body: InstrumentUpdate) =>
    request<Instrument>(`/api/instruments/${id}`, { method: "PATCH", json: body }),
  refreshPrices: () => request<{ refreshed_at: string | null; fetched: boolean }>("/api/portfolio/refresh", { method: "POST" }),
  summary: (ids: readonly number[]) => request<Summary>("/api/portfolio/summary", { query: { account_id: ids } }),
  history: (ids: readonly number[], from: IsoDate | null) =>
    request<History>("/api/portfolio/history", { query: { account_id: ids, from } }),
  exposure: (ids: readonly number[], day: IsoDate) =>
    request<Exposure>("/api/portfolio/exposure", { query: { account_id: ids, from: day, to: day } }),
  exposureHistory: (ids: readonly number[], from: IsoDate | null) =>
    request<Exposure>("/api/portfolio/exposure", { query: { account_id: ids, from } }),
  closed: (ids: readonly number[]) => request<Closed>("/api/portfolio/closed", { query: { account_id: ids } }),
  limits: () => request<Limit[]>("/api/portfolio/limits"),
  income: (ids: readonly number[], period: IncomePeriod) =>
    request<IncomeReport>("/api/analytics/income", { query: { account_id: ids, period } }),
  holdings: (ids: readonly number[], period: HoldingsPeriod) =>
    request<Holdings>("/api/analytics/holdings", { query: { account_id: ids, period } }),
  analytics: (ids: readonly number[], period: AnalyticsPeriod) =>
    request<Analytics>("/api/analytics", { query: { account_id: ids, period } }),
  positions: (ids: readonly number[]) => request<Position[]>("/api/positions", { query: { account_id: ids } }),
  positionPrices: (accountId: number, instrumentId: number, from: string | null) =>
    request<PriceChartData>(`/api/positions/${accountId}/${instrumentId}/prices`, { query: { from } }),
  position: (accountId: number, instrumentId: number) =>
    request<PositionDetail>(`/api/positions/${accountId}/${instrumentId}`),
  previewImport: (files: File[]) => request<ImportResult>("/api/imports/preview", { method: "POST", form: filesForm(files) }),
  commitImport: (files: File[]) => request<ImportResult>("/api/imports", { method: "POST", form: filesForm(files) }),
  createAccount: (body: AccountCreate) => request<Account>("/api/accounts", { method: "POST", json: body }),
  addTransaction: (body: TransactionIn) => request<Transaction>("/api/transactions", { method: "POST", json: body }),
  buyBonds: (body: BondIn) => request<BondOut>("/api/bonds", { method: "POST", json: body }),
  catalog: () => request<CatalogGroup[]>("/api/catalog"),
  addTicker: (ticker: string) => request<CatalogItem>("/api/catalog", { method: "POST", json: { ticker } }),
  scenarios: () => request<Scenario[]>("/api/scenarios"),
  scenario: (id: number) => request<Scenario>(`/api/scenarios/${id}`),
  createScenario: (body: ScenarioIn) => request<Scenario>("/api/scenarios", { method: "POST", json: body }),
  updateScenario: (id: number, body: ScenarioIn) =>
    request<Scenario>(`/api/scenarios/${id}`, { method: "PATCH", json: body }),
  deleteScenario: (id: number) => request<void>(`/api/scenarios/${id}`, { method: "DELETE" }),
  scenarioResult: (id: number, ids: readonly number[], period: AnalyticsPeriod) =>
    request<ScenarioResult>(`/api/scenarios/${id}/result`, { query: { account_id: ids, period } }),
  previewScenario: (body: ScenarioIn, ids: readonly number[]) =>
    request<ScenarioResult>("/api/scenarios/preview", { method: "POST", json: body, query: { account_id: ids, period: "all" } }),
  reviews: () => request<ReviewListItem[]>("/api/reviews"),
  review: (id: number) => request<Review>(`/api/reviews/${id}`),
  saveReview: (content: string, ids: readonly number[]) =>
    request<Review>("/api/reviews", { method: "POST", json: { content, account_ids: ids } }),
  deleteReview: (id: number) => request<void>(`/api/reviews/${id}`, { method: "DELETE" }),
  reviewPackage: (ids: readonly number[]) =>
    request<string>("/api/reviews/package", { query: { account_id: ids }, text: true }),
  createSavingsAccount: (body: SavingsAccountCreate) =>
    request<SavingsAccountOut>("/api/savings-accounts", { method: "POST", json: body }),
};
