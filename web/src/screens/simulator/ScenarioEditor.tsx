import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { errorMessage } from "../../api/messages";
import { keys } from "../../api/queryKeys";
import type { CatalogGroup, ScenarioIn } from "../../api/types";
import { ComparisonChart } from "../../charts/ComparisonChart";
import { addMonths, todayIso } from "../../format";
import { BackLink } from "../../ui/BackLink";
import { Confirm, Field, FormError } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { Segmented } from "../../ui/Segmented";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { chartData } from "./chart";
import {
  BASE_CONFLICT, BASES, NEW_DRAFT, difference, draftOf, newRecurring, newReplace, newShare, toBody, type Draft, type StepDraft,
} from "./model";
import styles from "./Simulator.module.css";
import { TargetSelect } from "./TargetSelect";
import { useDebounced } from "./useDebounced";

const PREVIEW_DELAY_MS = 500;
const PREVIEW_NAME = "Podgląd";
const HELD = "Twój portfel";
const LIST = "/analiza/symulator";
const DAYS = Array.from({ length: 28 }, (_, i) => String(i + 1));
const BASE_HINT: Record<Draft["base"], string> = {
  portfolio: "Twoje prawdziwe transakcje; klocki zmieniają je albo dokładają nowe pieniądze.",
  deposits: "Tylko Twoje wpłaty i wypłaty, z tymi samymi datami i kwotami; każda wpłata idzie według podziału.",
};

export function ScenarioEditor() {
  const { scenarioId } = useParams();
  const id = scenarioId ? Number(scenarioId) : null;
  const stored = useQuery({ queryKey: keys.scenario(id ?? 0), queryFn: () => api.scenario(id!), enabled: id !== null });
  const catalog = useQuery({ queryKey: keys.catalog, queryFn: api.catalog });
  const failed = id !== null && stored.isError ? stored : catalog.isError ? catalog : null;
  if (failed) return <div className={ui.page}><ErrorState error={failed.error} onRetry={() => void failed.refetch()} /></div>;
  if ((id !== null && !stored.data) || !catalog.data) return <div className={ui.page}><Skeleton rows={6} /></div>;
  return <EditorForm key={id ?? "new"} id={id} initial={stored.data ? draftOf(stored.data) : NEW_DRAFT} catalog={catalog.data} />;
}

function EditorForm({ id, initial, catalog }: { id: number | null; initial: Draft; catalog: CatalogGroup[] }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [accountIds, , ready] = useAccountSelection();
  const [draft, setDraft] = useState<Draft>(initial);
  const [tried, setTried] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const { body, errors } = toBody(draft);
  // A block that does not fit the starting point is explained at once; the rest after the first save attempt.
  const shownErrors = tried ? errors
    : Object.fromEntries(Object.entries(errors).filter(([, message]) => message === BASE_CONFLICT));
  // The name does not change the result, so the preview is asked without it (typing a name sends nothing).
  const check = toBody({ ...draft, name: PREVIEW_NAME });
  const previewBody = useDebounced(check.body, PREVIEW_DELAY_MS);
  const preview = useQuery({
    queryKey: keys.scenarioPreview(previewBody ?? {}, accountIds),
    queryFn: () => api.previewScenario(previewBody!, accountIds),
    enabled: ready && previewBody !== null,
    placeholderData: (previous) => previous,
  });

  const done = async (savedId: number) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.scenarios }),
      queryClient.invalidateQueries({ queryKey: keys.scenarioResults(savedId) }),
    ]);
    navigate(LIST);
  };
  const save = useMutation({
    mutationFn: (scenario: ScenarioIn) => (id === null ? api.createScenario(scenario) : api.updateScenario(id, scenario)),
    onSuccess: (saved) => done(saved.id),
  });
  const remove = useMutation({ mutationFn: () => api.deleteScenario(id!), onSuccess: () => done(id!) });

  const set = (change: Partial<Draft>) => setDraft((was) => ({ ...was, ...change }));
  const setShare = (index: number, change: Partial<Draft["allocation"][number]>) =>
    set({ allocation: draft.allocation.map((share, i) => (i === index ? { ...share, ...change } : share)) });
  const setStep = (index: number, change: Partial<StepDraft>) =>
    set({ steps: draft.steps.map((step, i) => (i === index ? ({ ...step, ...change } as StepDraft) : step)) });
  const chooseBase = (base: Draft["base"]) =>
    set({ base, allocation: base === "deposits" && draft.allocation.length === 0 ? [newShare()] : draft.allocation });

  function submit(event: FormEvent) {
    event.preventDefault();
    setTried(true);
    if (body) save.mutate(body);
  }

  const result = preview.data;
  const lines = result ? chartData([{ key: "preview", label: draft.name.trim() || PREVIEW_NAME, slot: 0, result }], true) : null;
  // Until the answer for the current blocks arrives the old one stays dimmed, without its difference.
  const stale = preview.isPlaceholderData || JSON.stringify(check.body) !== JSON.stringify(previewBody);
  const versus = result && !stale ? difference(result) : null;
  const firstError = Object.values(check.errors)[0];

  return (
    <div className={ui.page}>
      <BackLink to={LIST} label="Symulator" />
      <h1 className={ui.pageTitle}>{id === null ? "Nowy scenariusz" : "Scenariusz"}</h1>
      <form className={forms.form} onSubmit={submit} noValidate>
        <Field id="scenario-name" label="Nazwa" error={shownErrors.name}>
          <input id="scenario-name" value={draft.name} maxLength={80} onChange={(e) => set({ name: e.target.value })}
            aria-invalid={Boolean(shownErrors.name)} />
        </Field>
        <div className={forms.field}>
          <Segmented label="Punkt wyjścia" options={BASES} value={draft.base} onChange={chooseBase} />
          <small className={forms.hint}>{BASE_HINT[draft.base]}</small>
        </div>

        {draft.base === "deposits" && (
          <fieldset className={styles.block}>
            <legend>Na co idą wpłaty</legend>
            {draft.allocation.map((share, index) => (
              <div key={index} className={styles.shareRow}>
                <TargetSelect id={`share-${index}-target`} label="Cel" catalog={catalog} bonds value={share.target}
                  onChange={(target) => setShare(index, { target })} />
                <Field id={`share-${index}-pct`} label="Udział (%)" error={shownErrors[`allocation.${index}.pct`]}>
                  <input id={`share-${index}-pct`} inputMode="decimal" value={share.pct}
                    onChange={(e) => setShare(index, { pct: e.target.value })} />
                </Field>
                {draft.allocation.length > 1 && (
                  <button type="button" className={forms.link}
                    onClick={() => set({ allocation: draft.allocation.filter((_, i) => i !== index) })}>Usuń cel</button>
                )}
              </div>
            ))}
            {shownErrors.allocation && <small className={forms.error}>{shownErrors.allocation}</small>}
            <button type="button" className={forms.link}
              onClick={() => set({ allocation: [...draft.allocation, { ...newShare(), pct: "" }] })}>Dodaj cel</button>
          </fieldset>
        )}

        {draft.steps.map((step, index) => (
          <fieldset key={index} className={styles.block}>
            <legend>{step.kind === "replace" ? "Podmień instrument" : "Dopłacaj co miesiąc"}</legend>
            {step.kind === "replace" ? (
              <>
                <TargetSelect id={`step-${index}-from`} label="Zamiast" catalog={catalog} groups={[HELD]} value={step.from}
                  onChange={(from) => setStep(index, { from })} error={shownErrors[`steps.${index}.from`]} />
                <TargetSelect id={`step-${index}-to`} label="Kupuj" catalog={catalog} value={step.to}
                  onChange={(to) => setStep(index, { to })} error={shownErrors[`steps.${index}.to`]} />
              </>
            ) : (
              <>
                <div className={forms.row}>
                  <Field id={`step-${index}-amount`} label="Kwota co miesiąc (zł)" error={shownErrors[`steps.${index}.amount`]}>
                    <input id={`step-${index}-amount`} inputMode="decimal" value={step.amount}
                      onChange={(e) => setStep(index, { amount: e.target.value })} />
                  </Field>
                  <Field id={`step-${index}-day`} label="Dzień miesiąca">
                    <select id={`step-${index}-day`} value={step.day} onChange={(e) => setStep(index, { day: e.target.value })}>
                      {DAYS.map((day) => <option key={day} value={day}>{day}</option>)}
                    </select>
                  </Field>
                </div>
                <div className={forms.row}>
                  <Field id={`step-${index}-start`} label="Od miesiąca" error={shownErrors[`steps.${index}.start`]}>
                    <input id={`step-${index}-start`} type="month" min="2016-01" placeholder="RRRR-MM" value={step.start}
                      onChange={(e) => setStep(index, { start: e.target.value })} />
                  </Field>
                  <Field id={`step-${index}-end`} label="Do miesiąca" hint="puste: do dziś" error={shownErrors[`steps.${index}.end`]}>
                    <input id={`step-${index}-end`} type="month" min="2016-01" placeholder="RRRR-MM" value={step.end}
                      onChange={(e) => setStep(index, { end: e.target.value })} />
                  </Field>
                </div>
                <TargetSelect id={`step-${index}-target`} label="Na co" catalog={catalog} bonds value={step.target}
                  onChange={(target) => setStep(index, { target })} />
                <label className={styles.check}>
                  <input type="checkbox" checked={step.ike} onChange={(e) => setStep(index, { ike: e.target.checked })} />
                  Na IKE (obligacje bez podatku)
                </label>
              </>
            )}
            <button type="button" className={forms.link}
              onClick={() => set({ steps: draft.steps.filter((_, i) => i !== index) })}>Usuń klocek</button>
          </fieldset>
        ))}
        <div className={forms.actions}>
          {draft.base === "portfolio" && (
            <button type="button" className={ui.secondary} onClick={() => set({ steps: [...draft.steps, newReplace()] })}>
              Podmień instrument
            </button>
          )}
          <button type="button" className={ui.secondary}
            onClick={() => set({ steps: [...draft.steps, newRecurring(addMonths(todayIso(), -12).slice(0, 7))] })}>
            Dopłacaj co miesiąc
          </button>
        </div>
        <AddTicker />

        <section className={ui.section} aria-labelledby="preview-title">
          <h2 id="preview-title" className={ui.sectionTitle}>Podgląd</h2>
          {check.body === null ? <p className={styles.hint}>Podgląd pojawi się po poprawce: {firstError}</p>
            : preview.isError ? <ErrorState error={preview.error} onRetry={() => void preview.refetch()} />
            : !result || !lines ? <Skeleton rows={0} chart />
            : (
              <>
                {stale ? <p className={styles.diff} role="status">Liczę podgląd…</p>
                  : versus && <p className={styles.diff}>Względem portfela: {versus}</p>}
                <div className={stale ? styles.stale : undefined} aria-busy={stale}><ComparisonChart {...lines} /></div>
                {result.notes.length > 0 && <ul className={styles.notes}>{result.notes.map((note) => <li key={note}>{note}</li>)}</ul>}
              </>
            )}
        </section>

        <FormError message={save.isError ? errorMessage(save.error) : remove.isError ? errorMessage(remove.error) : null} />
        <div className={forms.actions}>
          <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Zapisz scenariusz</button>
          {id !== null && !confirming && (
            <button type="button" className={forms.danger} onClick={() => setConfirming(true)}>Usuń scenariusz</button>
          )}
        </div>
        {confirming && (
          <Confirm question={`Usunąć scenariusz „${initial.name}”?`} confirmLabel="Usuń" busy={remove.isPending}
            onConfirm={() => remove.mutate()} onCancel={() => setConfirming(false)} />
        )}
      </form>
    </div>
  );
}

function AddTicker() {
  const queryClient = useQueryClient();
  const [ticker, setTicker] = useState("");
  const add = useMutation({
    mutationFn: () => api.addTicker(ticker.trim()),
    onSuccess: async () => {
      setTicker("");
      await queryClient.invalidateQueries({ queryKey: keys.catalog });
    },
  });
  return (
    <div className={styles.addTicker}>
      <Field id="add-ticker" label="Brakuje instrumentu? Dodaj ticker z Yahoo"
        error={add.isError ? errorMessage(add.error) : undefined}
        hint={add.data ? `Dodano: ${add.data.name}` : "np. VWCE.DE albo AAPL.US"}>
        <input id="add-ticker" value={ticker} onChange={(e) => setTicker(e.target.value)} />
      </Field>
      <button type="button" className={ui.secondary} disabled={!ticker.trim() || add.isPending} onClick={() => add.mutate()}>
        Dodaj ticker
      </button>
    </div>
  );
}
