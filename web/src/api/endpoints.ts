import { request } from "./client";
import type {
  Account, Exposure, History, ImportResult, IsoDate, Position, PositionDetail, RegisterIn, Summary, TokenOut, UserOut,
} from "./types";

function filesForm(files: File[]): FormData {
  const form = new FormData();
  for (const file of files) form.append("files", file, file.name);
  return form;
}

export const api = {
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
};
