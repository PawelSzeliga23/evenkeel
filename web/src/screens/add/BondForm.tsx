import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { ApiError } from "../../api/client";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Account, BondIn } from "../../api/types";
import { formatMoney, parseAmount, todayIso } from "../../format";
import {
  AccountChoice, Field, FormError, NEW_ACCOUNT, accountFor, formErrors, useInvalidateAfterSave, type FormErrors,
} from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { Segmented } from "../../ui/Segmented";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";

const WRAPPERS: { value: Account["wrapper"]; label: string }[] = [
  { value: "regular", label: "Zwykłe" }, { value: "ike", label: "IKE" }, { value: "ikze", label: "IKZE" },
];
const RATE_HINT = "Podaj oprocentowanie, np. 5,35.";

export function BondForm() {
  const navigate = useNavigate();
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const bondAccounts = (accounts.data ?? []).filter((a) => a.kind === "bonds");
  const [account, setAccount] = useState("");
  const [newName, setNewName] = useState("Obligacje");
  const [wrapper, setWrapper] = useState<Account["wrapper"]>("regular");
  const [quantity, setQuantity] = useState("");
  const [date, setDate] = useState(todayIso());
  const [needsRates, setNeedsRates] = useState(false);
  const [firstRate, setFirstRate] = useState("");
  const [margin, setMargin] = useState("");
  const [errors, setErrors] = useState<FormErrors>({ fields: {}, general: null });
  const invalidate = useInvalidateAfterSave();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (accounts.data && account === "") {
      const first = accounts.data.find((a) => a.kind === "bonds");
      setAccount(first ? String(first.id) : NEW_ACCOUNT);
    }
  }, [accounts.data, account]);

  const count = /^\d+$/.test(quantity.trim()) ? Number(quantity.trim()) : null;

  const save = useMutation({
    mutationFn: async (rates: { first_period_rate: string; margin: string } | null) => {
      const accountId = await accountFor(account, { name: newName.trim(), kind: "bonds", wrapper });
      if (account === NEW_ACCOUNT) {
        // A retry after series_unknown must stay on the account just created instead of creating another one.
        setAccount(String(accountId));
        setNewName("");
        await queryClient.invalidateQueries({ queryKey: keys.accounts });
      }
      const body: BondIn = { account_id: accountId, bond_type: "EDO", quantity: count!, purchase_date: date, ...(rates ?? {}) };
      return api.buyBonds(body);
    },
    onSuccess: async (bond) => {
      await invalidate();
      navigate(`/pozycje/obligacje/${bond.id}`);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "series_unknown") {
        setNeedsRates(true);
        setErrors({ fields: {}, general: error.message });
        return;
      }
      setErrors(formErrors(error, { purchase_in_future: "purchase_date", wrong_account_kind: "account_id" }));
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const fields: Record<string, string> = {};
    if (count === null || count < 1) fields.quantity = "Podaj liczbę całkowitą, co najmniej 1.";
    if (account === NEW_ACCOUNT && !newName.trim()) fields.name = "Podaj nazwę konta.";
    let rates: { first_period_rate: string; margin: string } | null = null;
    if (needsRates) {
      const first = parseAmount(firstRate, 4);
      const extra = parseAmount(margin, 4);
      if (first === null) fields.first_period_rate = RATE_HINT;
      if (extra === null) fields.margin = RATE_HINT;
      if (first !== null && extra !== null) rates = { first_period_rate: first, margin: extra };
    }
    setErrors({ fields, general: null });
    if (Object.keys(fields).length === 0) save.mutate(rates);
  }

  if (accounts.isPending) return <div className={ui.page}><Skeleton rows={4} /></div>;
  if (accounts.isError) return <div className={ui.page}><ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} /></div>;

  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Obligacja</h1>
      <form className={forms.form} onSubmit={submit} noValidate>
        <Field id="bond-type" label="Rodzaj" hint="Na razie aplikacja wycenia obligacje 10-letnie EDO.">
          <select id="bond-type" value="EDO" disabled><option value="EDO">EDO</option></select>
        </Field>
        <AccountChoice id="bond-account" accounts={bondAccounts} value={account} onChange={setAccount} error={errors.fields.account_id} />
        {account === NEW_ACCOUNT && (
          <>
            <Field id="bond-new-name" label="Nazwa nowego konta" error={errors.fields.name}>
              <input id="bond-new-name" value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={100} />
            </Field>
            <Segmented label="Rodzaj konta" options={WRAPPERS} value={wrapper} onChange={setWrapper} />
          </>
        )}
        <div className={forms.row}>
          <Field id="bond-quantity" label="Liczba obligacji" error={errors.fields.quantity}
            hint={count ? `Wartość nominalna ${formatMoney(String(count * 100))}` : "Jedna obligacja to 100 zł."}>
            <input id="bond-quantity" inputMode="numeric" value={quantity} onChange={(e) => setQuantity(e.target.value)}
              aria-invalid={Boolean(errors.fields.quantity)} />
          </Field>
          <Field id="bond-date" label="Data zakupu" error={errors.fields.purchase_date}>
            <input id="bond-date" type="date" value={date} max={todayIso()} onChange={(e) => setDate(e.target.value)} />
          </Field>
        </div>
        {needsRates && (
          <div className={forms.row}>
            <Field id="bond-first-rate" label="Oprocentowanie w pierwszym roku (%)" error={errors.fields.first_period_rate}
              hint="Z listu emisyjnego serii.">
              <input id="bond-first-rate" inputMode="decimal" value={firstRate} onChange={(e) => setFirstRate(e.target.value)} />
            </Field>
            <Field id="bond-margin" label="Marża (p.p.)" error={errors.fields.margin} hint="Dodawana do inflacji od 2. roku.">
              <input id="bond-margin" inputMode="decimal" value={margin} onChange={(e) => setMargin(e.target.value)} />
            </Field>
          </div>
        )}
        <FormError message={errors.general} />
        <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Zapisz zakup</button>
      </form>
    </div>
  );
}
