import { request } from "./client";
import type {
  Account, AccountCreate, BondDetail, BondIn, BondOut, Exposure, History, HistoryFilters, HistoryPage, ImportResult, IsoDate, Position, PositionDetail, RegisterIn, SavingsAccountCreate, SavingsAccountOut, SavingsFlowOut, Summary, TokenOut, Transaction, TransactionIn, UserOut,
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
      query: { account_id: filters.account_id, type: filters.type, from: filters.from, to: filters.to, q: filters.q, cursor },
    }),
  login: (email: string, password: string) =>
    request<TokenOut>("/api/auth/login", { method: "POST", json: { email, password }, auth: false }),
  register: (body: RegisterIn) => request<UserOut>("/api/auth/register", { method: "POST", json: body, auth: false }),
  logout: () => request<void>("/api/auth/logout", { method: "POST", auth: false }),
  me: () => request<UserOut>("/api/auth/me"),
  accounts: () => request<Account[]>("/api/accounts"),
  summary: (accountId: number | null) => request<Summary>("/api/portfolio/summary", { query: { account_id: accountId } }),
  history: (accountId: number | null, from: IsoDate | null) =>
    request<History>("/api/portfolio/history", { query: { account_id: accountId, from } }),
  exposure: (accountId: number | null, day: IsoDate) =>
    request<Exposure>("/api/portfolio/exposure", { query: { account_id: accountId, from: day, to: day } }),
  positions: (accountId: number | null) => request<Position[]>("/api/positions", { query: { account_id: accountId } }),
  position: (accountId: number, instrumentId: number) =>
    request<PositionDetail>(`/api/positions/${accountId}/${instrumentId}`),
  previewImport: (files: File[]) => request<ImportResult>("/api/imports/preview", { method: "POST", form: filesForm(files) }),
  commitImport: (files: File[]) => request<ImportResult>("/api/imports", { method: "POST", form: filesForm(files) }),
  createAccount: (body: AccountCreate) => request<Account>("/api/accounts", { method: "POST", json: body }),
  addTransaction: (body: TransactionIn) => request<Transaction>("/api/transactions", { method: "POST", json: body }),
  buyBonds: (body: BondIn) => request<BondOut>("/api/bonds", { method: "POST", json: body }),
  createSavingsAccount: (body: SavingsAccountCreate) =>
    request<SavingsAccountOut>("/api/savings-accounts", { method: "POST", json: body }),
};
