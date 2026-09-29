import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ApiError } from "../api/client";
import { api } from "../api/endpoints";
import { errorMessage } from "../api/messages";
import { keys } from "../api/queryKeys";
import type { Account, AccountCreate } from "../api/types";
import styles from "./forms.module.css";

export const AMOUNT_HINT = "Podaj kwotę, np. 1\u00a0250,50.";
export const NEW_ACCOUNT = "new";

export function Field({ id, label, error, hint, children }: {
  id: string; label: string; error?: string; hint?: ReactNode; children: ReactNode;
}) {
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      {children}
      {error ? <small className={styles.error}>{error}</small> : hint && <small className={styles.hint}>{hint}</small>}
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  return message ? <p className={styles.error} role="alert">{message}</p> : null;
}

export interface FormErrors { fields: Record<string, string>; general: string | null }

/** An API error as messages at the fields they are about (validation `loc`, or a known `code`), else a general one. */
export function formErrors(error: unknown, byCode: Record<string, string> = {}): FormErrors {
  if (error instanceof ApiError) {
    if (error.code === "validation_error") {
      const fields: Record<string, string> = {};
      for (const item of (error.details.errors as { loc?: unknown[] }[] | undefined) ?? []) {
        const name = [...(item.loc ?? [])].reverse().find((part): part is string => typeof part === "string" && part !== "body");
        if (name) fields[name] = "Sprawdź tę wartość.";
      }
      if (Object.keys(fields).length > 0) return { fields, general: null };
    }
    const field = byCode[error.code];
    if (field) return { fields: { [field]: error.message }, general: null };
  }
  return { fields: {}, general: errorMessage(error) };
}

export function AccountChoice({ id, accounts, value, onChange, error }: {
  id: string; accounts: Account[]; value: string; onChange: (value: string) => void; error?: string;
}) {
  return (
    <Field id={id} label="Konto" error={error}>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        {accounts.map((account) => <option key={account.id} value={String(account.id)}>{account.name}</option>)}
        <option value={NEW_ACCOUNT}>Nowe konto…</option>
      </select>
    </Field>
  );
}

/** The chosen account's id, creating the new account first when "Nowe konto…" was chosen. */
export async function accountFor(choice: string, create: AccountCreate): Promise<number> {
  return choice === NEW_ACCOUNT ? (await api.createAccount(create)).id : Number(choice);
}

export function useInvalidateAfterSave(): () => Promise<void> {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.portfolio }),
      queryClient.invalidateQueries({ queryKey: keys.accounts }),
    ]);
  };
}
