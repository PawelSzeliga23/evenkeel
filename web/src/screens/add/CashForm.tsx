import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { CashOperationType } from "../../api/types";
import { isPositive, parseAmount, todayIso } from "../../format";
import {
  AMOUNT_HINT, AccountChoice, Field, FormError, NEW_ACCOUNT, accountFor, formErrors, useInvalidateAfterSave,
  type FormErrors,
} from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { Segmented } from "../../ui/Segmented";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";

const TYPES: { value: CashOperationType; label: string }[] = [
  { value: "deposit", label: "Wpłata" }, { value: "withdrawal", label: "Wypłata" },
  { value: "interest", label: "Odsetki" }, { value: "fee", label: "Opłata" },
];
const NO_ERRORS: FormErrors = { fields: {}, general: null };

export function CashForm() {
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const cash = (accounts.data ?? []).filter((a) => a.kind === "cash");
  const [account, setAccount] = useState("");
  const [newName, setNewName] = useState("");
  const [type, setType] = useState<CashOperationType>("deposit");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayIso());
  const [comment, setComment] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const invalidate = useInvalidateAfterSave();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (accounts.data && account === "") {
      const first = accounts.data.find((a) => a.kind === "cash");
      setAccount(first ? String(first.id) : NEW_ACCOUNT);
    }
  }, [accounts.data, account]);

  const save = useMutation({
    mutationFn: async (value: string) => {
      const accountId = await accountFor(account, { name: newName.trim(), kind: "cash", wrapper: "regular" });
      if (account === NEW_ACCOUNT) {
        // Keep a retry or "Dodaj kolejną" on the account just created instead of creating another one.
        setAccount(String(accountId));
        setNewName("");
        await queryClient.invalidateQueries({ queryKey: keys.accounts });
      }
      return api.addTransaction({ account_id: accountId, type, amount: value, date, comment: comment.trim() });
    },
    onSuccess: () => invalidate(),
    onError: (error) => setErrors(formErrors(error, { date_in_future: "date", wrong_account_kind: "account_id" })),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = parseAmount(amount);
    const fields: Record<string, string> = {};
    if (value === null || !isPositive(value)) fields.amount = AMOUNT_HINT;
    if (account === NEW_ACCOUNT && !newName.trim()) fields.name = "Podaj nazwę konta.";
    setErrors({ fields, general: null });
    if (Object.keys(fields).length === 0 && value !== null) save.mutate(value);
  }

  if (accounts.isPending) return <div className={ui.page}><Skeleton rows={4} /></div>;
  if (accounts.isError) return <div className={ui.page}><ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} /></div>;

  if (save.isSuccess) {
    return (
      <div className={ui.page}>
        <h1 className={ui.pageTitle}>Operacja gotówkowa</h1>
        <div className={forms.success}>
          <p>Operacja zapisana.</p>
          <div className={forms.actions}>
            <button type="button" className={ui.primaryButton} onClick={() => { save.reset(); setAmount(""); setComment(""); }}>
              Dodaj kolejną
            </button>
            <Link className={ui.secondary} to="/pozycje">Zobacz pozycje</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Operacja gotówkowa</h1>
      <form className={forms.form} onSubmit={submit} noValidate>
        <AccountChoice id="cash-account" accounts={cash} value={account} onChange={setAccount} error={errors.fields.account_id} />
        {account === NEW_ACCOUNT && (
          <Field id="cash-new-name" label="Nazwa nowego konta" error={errors.fields.name}>
            <input id="cash-new-name" value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={100} />
          </Field>
        )}
        <Segmented label="Rodzaj operacji" options={TYPES} value={type} onChange={setType} />
        <div className={forms.row}>
          <Field id="cash-amount" label="Kwota" error={errors.fields.amount} hint="W złotych, bez znaku minus.">
            <input id="cash-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)}
              aria-invalid={Boolean(errors.fields.amount)} />
          </Field>
          <Field id="cash-date" label="Data" error={errors.fields.date}>
            <input id="cash-date" type="date" value={date} max={todayIso()} onChange={(e) => setDate(e.target.value)}
              aria-invalid={Boolean(errors.fields.date)} />
          </Field>
        </div>
        <Field id="cash-comment" label="Opis" error={errors.fields.comment}>
          <input id="cash-comment" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={200} />
        </Field>
        <FormError message={errors.general} />
        <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Zapisz operację</button>
      </form>
    </div>
  );
}
