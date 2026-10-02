import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useParams } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Account, SavingsAccountOut, SavingsFlowOut } from "../../api/types";
import { formatDate, formatMoney, formatPercent, isPositive, parseAmount, todayIso, toCents } from "../../format";
import { HeroAmount, Money } from "../../ui/Amount";
import { AMOUNT_HINT, Confirm, Field, FormError, formErrors, useInvalidateAfterSave, type FormErrors } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { Segmented } from "../../ui/Segmented";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { TagsSection } from "../../tags/TagsSection";
import { Back } from "../bonds/BondDetailScreen";
import styles from "../bonds/Details.module.css";

const CAPITALIZATION = { daily: "dzienna", monthly: "miesięczna", quarterly: "kwartalna" } as const;
const WRAPPER = { regular: "zwykłe", ike: "IKE", ikze: "IKZE" } as const;
const MONTHS = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień"];
const NO_ERRORS: FormErrors = { fields: {}, general: null };

const QUARTERS = ["I", "II", "III", "IV"];
const periodName = (iso: string, quarterly: boolean) => {
  const month = Number(iso.slice(5, 7));
  return quarterly ? `${QUARTERS[Math.ceil(month / 3) - 1]} kwartał ${iso.slice(0, 4)}` : `${MONTHS[month - 1]} ${iso.slice(0, 4)}`;
};
const flowLabel = (flow: SavingsFlowOut) => (toCents(flow.amount) > 0n ? "wpłatę" : "wypłatę");

function FlowForm({ accountId, onDone }: { accountId: number; onDone: () => void }) {
  const invalidate = useInvalidateAfterSave();
  const [direction, setDirection] = useState<"in" | "out">("in");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(todayIso());
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const save = useMutation({
    mutationFn: (value: string) => api.addSavingsFlow(accountId, { date, amount: direction === "out" ? `-${value}` : value, note: note.trim() }),
    onSuccess: async () => { await invalidate(); onDone(); },
    onError: (error) => setErrors(formErrors(error, { insufficient_balance: "amount", date_in_future: "date" })),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    const value = parseAmount(amount);
    if (value === null || !isPositive(value)) return setErrors({ fields: { amount: AMOUNT_HINT }, general: null });
    setErrors(NO_ERRORS);
    save.mutate(value);
  }
  return (
    <form className={styles.panel} onSubmit={submit} noValidate>
      <Segmented label="Rodzaj" options={[{ value: "in", label: "Wpłata" }, { value: "out", label: "Wypłata" }]} value={direction} onChange={setDirection} />
      <div className={forms.row}>
        <Field id="flow-amount" label="Kwota" error={errors.fields.amount}>
          <input id="flow-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </Field>
        <Field id="flow-date" label="Data" error={errors.fields.date}>
          <input id="flow-date" type="date" value={date} max={todayIso()} onChange={(e) => setDate(e.target.value)} />
        </Field>
      </div>
      <Field id="flow-note" label="Opis"><input id="flow-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} /></Field>
      <FormError message={errors.general} />
      <div className={styles.actions}>
        <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Zapisz</button>
        <button type="button" className={forms.cancel} onClick={onDone}>Anuluj</button>
      </div>
    </form>
  );
}

function RateForm({ accountId, onDone }: { accountId: number; onDone: () => void }) {
  const invalidate = useInvalidateAfterSave();
  const [rate, setRate] = useState("");
  const [from, setFrom] = useState(todayIso());
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const save = useMutation({
    mutationFn: (value: string) => api.addSavingsRate(accountId, { valid_from: from, annual_rate: value }),
    onSuccess: async () => { await invalidate(); onDone(); },
    onError: (error) => setErrors(formErrors(error, { duplicate_date: "valid_from" })),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    const value = parseAmount(rate, 4);
    if (value === null) return setErrors({ fields: { annual_rate: "Podaj oprocentowanie, np. 5,35." }, general: null });
    setErrors(NO_ERRORS);
    save.mutate(value);
  }
  return (
    <form className={styles.panel} onSubmit={submit} noValidate>
      <div className={forms.row}>
        <Field id="rate-value" label="Nowe oprocentowanie (%)" error={errors.fields.annual_rate}>
          <input id="rate-value" inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} />
        </Field>
        <Field id="rate-from" label="Obowiązuje od" error={errors.fields.valid_from}>
          <input id="rate-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </Field>
      </div>
      <FormError message={errors.general} />
      <div className={styles.actions}>
        <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Zapisz oprocentowanie</button>
        <button type="button" className={forms.cancel} onClick={onDone}>Anuluj</button>
      </div>
    </form>
  );
}

function Detail({ account, savings }: { account: Account; savings: SavingsAccountOut }) {
  const invalidate = useInvalidateAfterSave();
  const [panel, setPanel] = useState<"none" | "flow" | "rate">("none");
  const [deleting, setDeleting] = useState<SavingsFlowOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const remove = useMutation({
    mutationFn: (flow: SavingsFlowOut) => api.deleteSavingsFlow(account.id, flow.id),
    onSuccess: async () => { setError(null); await invalidate(); setDeleting(null); },
    onError: (err) => { setDeleting(null); setError(formErrors(err).general); },
  });
  const { summary } = savings;
  const since = [...savings.capitalizations].pop()?.credited_on;

  return (
    <>
      <section className={styles.head} aria-label="Podsumowanie konta">
        <span className="dim">{`Konto oszczędnościowe ${WRAPPER[account.wrapper]}`}</span>
        <h1 className={styles.name}>{account.name}</h1>
        <HeroAmount value={summary.balance} size="m" />
        <span className="dim num">{`Odsetki narosłe od ostatniej kapitalizacji: ${formatMoney(summary.accrued)}`}</span>
        {savings.rates.length > 0 && savings.rates[0]!.valid_from > todayIso() && (
          <span className="flag">{`Oprocentowanie od ${formatDate(savings.rates[0]!.valid_from)}, do tego czasu 0 %.`}</span>
        )}
      </section>

      <TagsSection tags={savings.tags} target={{ savings: true }} accountId={account.id} accountName={account.name} />

      <dl className={ui.kv}>
        <dt>Wpłacono (netto)</dt><dd><Money value={summary.deposits} /></dd>
        <dt>Odsetki dopisane (netto)</dt><dd><Money value={summary.interest_net} /></dd>
        <dt>Podatek</dt><dd><Money value={summary.tax} /></dd>
        <dt>Oprocentowanie teraz</dt><dd>{formatPercent(summary.current_rate, { sign: false })}</dd>
        <dt>Kapitalizacja</dt><dd>{CAPITALIZATION[savings.capitalization]}</dd>
        {since && <><dt>Ostatnia kapitalizacja</dt><dd>{formatDate(since)}</dd></>}
      </dl>

      <div className={styles.actions}>
        <button type="button" className={ui.secondary} onClick={() => setPanel("flow")}>Wpłata lub wypłata</button>
        <button type="button" className={ui.secondary} onClick={() => setPanel("rate")}>Zmień oprocentowanie</button>
      </div>
      {panel === "flow" && <FlowForm accountId={account.id} onDone={() => setPanel("none")} />}
      {panel === "rate" && <RateForm accountId={account.id} onDone={() => setPanel("none")} />}

      <section className={ui.section} aria-labelledby="savings-flows">
        <h2 id="savings-flows" className={ui.sectionTitle}>Wpłaty i wypłaty</h2>
        <ul className={styles.list}>
          {[...savings.flows].reverse().map((flow) => (
            <li key={flow.id} className={styles.entry}>
              <span className={styles.entryName}>
                <b>{formatDate(flow.date)}</b>
                {flow.note && <small>{flow.note}</small>}
              </span>
              <span className={styles.entryAmount}>
                <Money value={flow.amount} sign tone />
                <button type="button" className={forms.link} onClick={() => { setError(null); setDeleting(flow); }}>Usuń</button>
              </span>
            </li>
          ))}
        </ul>
        {deleting && (
          <Confirm
            question={`Usunąć ${flowLabel(deleting)} ${formatMoney(deleting.amount.replace("-", ""))} z ${formatDate(deleting.date)}?`}
            confirmLabel="Usuń" busy={remove.isPending} onConfirm={() => { setError(null); remove.mutate(deleting); }} onCancel={() => { setError(null); setDeleting(null); }}
          />
        )}
        <FormError message={error} />
      </section>

      <section className={ui.section} aria-labelledby="savings-interest">
        <h2 id="savings-interest" className={ui.sectionTitle}>Odsetki</h2>
        <ul className={styles.list}>
          {[...savings.capitalizations].reverse().map((cap) => (
            <li key={cap.period_end} className={styles.entry}>
              <span className={styles.entryName}><b>{periodName(cap.period_end, savings.capitalization === "quarterly")}</b><small className="num">{`podatek ${formatMoney(cap.tax)}`}</small></span>
              <span className={styles.entryAmount}><Money value={cap.net} sign tone /></span>
            </li>
          ))}
        </ul>
      </section>

      <section className={ui.section} aria-labelledby="savings-rates">
        <h2 id="savings-rates" className={ui.sectionTitle}>Oprocentowanie</h2>
        <ul className={styles.list}>
          {[...savings.rates].reverse().map((rate) => (
            <li key={rate.id} className={styles.entry}>
              <span className={styles.entryName}><b>{`od ${formatDate(rate.valid_from)}`}</b></span>
              <span className={styles.entryAmount}><span className="num">{formatPercent(rate.annual_rate, { sign: false })}</span></span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

export function SavingsDetailScreen() {
  const id = Number(useParams().accountId);
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const savings = useQuery({ queryKey: keys.savings(id), queryFn: () => api.savings(id), enabled: Number.isInteger(id) });
  const account = accounts.data?.find((a) => a.id === id);
  const settled = !Number.isInteger(id) || savings.isError || savings.data !== undefined;
  const notFound = settled && (!Number.isInteger(id) || (accounts.data !== undefined && !account));
  const failed = accounts.isError ? accounts : savings.isError ? savings : null;
  return (
    <div className={ui.page}>
      <Back />
      {notFound ? <p role="alert">Nie znaleziono konta.</p>
        : failed ? <ErrorState error={failed.error} onRetry={() => void failed.refetch()} />
        : !account || !savings.data ? <Skeleton rows={6} />
          : <Detail account={account} savings={savings.data} />}
    </div>
  );
}
