import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Account, AccountUpdate } from "../../api/types";
import { BackLink } from "../../ui/BackLink";
import { Field, FormError, formErrors, useInvalidateAfterSave, type FormErrors } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { ACCOUNT_KIND, WRAPPER_OPTIONS, usageSummary } from "./model";
import styles from "./Settings.module.css";

const NO_ERRORS: FormErrors = { fields: {}, general: null };

function DeleteAccount({ account }: { account: Account }) {
  const navigate = useNavigate();
  const invalidate = useInvalidateAfterSave();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const usage = useQuery({ queryKey: keys.accountUsage(account.id), queryFn: () => api.accountUsage(account.id), enabled: open });
  const remove = useMutation({
    mutationFn: () => api.deleteAccount(account.id),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: keys.accountUsage(account.id) });
      navigate("/ustawienia", { state: { notice: "Konto usunięte." } });
      void invalidate();
    },
  });

  if (!open) {
    return (
      <section className={styles.danger} aria-label="Usuwanie konta">
        <button type="button" className={`${forms.danger} ${styles.start}`} onClick={() => setOpen(true)}>Usuń konto</button>
      </section>
    );
  }
  const lost = usage.data ? usageSummary(usage.data) : "";
  return (
    <section className={`${styles.danger} ${styles.panel}`} aria-label="Usuwanie konta">
      {usage.isPending ? <Skeleton rows={1} />
        : usage.isError ? <ErrorState error={usage.error} onRetry={() => void usage.refetch()} />
        : <p>
            Usunięcie konta „{account.name}” skasuje {lost ? `także: ${lost}` : "puste konto"}. Tego nie da się cofnąć.
          </p>}
      <Field id="delete-confirm" label="Wpisz nazwę konta, aby potwierdzić">
        <input id="delete-confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
      </Field>
      <FormError message={remove.isError ? formErrors(remove.error).general : null} />
      <div className={forms.actions}>
        <button type="button" className={forms.danger} disabled={typed.trim() !== account.name || remove.isPending}
          onClick={() => remove.mutate()}>Usuń na zawsze</button>
        <button type="button" className={forms.cancel} onClick={() => { setOpen(false); setTyped(""); }}>Anuluj</button>
      </div>
    </section>
  );
}

function EditAccount({ account }: { account: Account }) {
  const invalidate = useInvalidateAfterSave();
  const [name, setName] = useState(account.name);
  const [wrapper, setWrapper] = useState(account.wrapper);
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const save = useMutation({
    mutationFn: (body: AccountUpdate) => api.updateAccount(account.id, body),
    onSuccess: () => invalidate(),
    onError: (error) => setErrors(formErrors(error)),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const body: AccountUpdate = {};
    if (name.trim() !== account.name) body.name = name.trim();
    if (wrapper !== account.wrapper) body.wrapper = wrapper;
    setErrors(name.trim() ? NO_ERRORS : { fields: { name: "Podaj nazwę konta." }, general: null });
    if (name.trim() && Object.keys(body).length === 0) {
      setErrors({ fields: {}, general: "Brak zmian do zapisania." });
      return;
    }
    if (name.trim()) save.mutate(body);
  }

  return (
    <form className={forms.form} onSubmit={submit} noValidate>
      <Field id="account-name" label="Nazwa" error={errors.fields.name}>
        <input id="account-name" value={name} maxLength={100} onChange={(e) => { setName(e.target.value); save.reset(); }}
          aria-invalid={Boolean(errors.fields.name)} />
      </Field>
      <Field id="account-wrapper" label="Typ konta" error={errors.fields.wrapper}
        hint="Od typu zależy podatek od odsetek i limit wpłat IKE/IKZE; zmiana przelicza wycenę.">
        <Segmented label="Typ konta" options={WRAPPER_OPTIONS} value={wrapper} onChange={(v) => { setWrapper(v); save.reset(); }} />
      </Field>
      <FormError message={errors.general} />
      {save.isSuccess && <p role="status">Zapisano.</p>}
      <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Zapisz zmiany</button>
    </form>
  );
}

export function AccountScreen() {
  const id = Number(useParams().accountId);
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const account = accounts.data?.find((a) => a.id === id);

  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      {accounts.isPending ? <Skeleton rows={3} />
        : accounts.isError ? <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
        : !account ? <EmptyState title="Nie znaleziono konta." />
        : (
          <>
            <div>
              <h1 className={ui.pageTitle}>{account.name}</h1>
              <p className="dim">
                {ACCOUNT_KIND[account.kind]}{account.external_account_number ? ` · nr ${account.external_account_number}` : ""} · {account.currency}
              </p>
            </div>
            <EditAccount key={account.id} account={account} />
            <DeleteAccount account={account} />
          </>
        )}
    </div>
  );
}
