import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { api } from "../../api/endpoints";
import { errorMessage } from "../../api/messages";
import { keys } from "../../api/queryKeys";
import type { Instrument } from "../../api/types";
import { formatDate, formatDecimal, parseAmount } from "../../format";
import { BackLink } from "../../ui/BackLink";
import { Field } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { hasPriceProblem, problemsFirst } from "./model";
import styles from "./Settings.module.css";

const SAVED = "Zapisano. Ceny pobiorę przy najbliższej aktualizacji.";
const SPREAD_SAVED = "Zapisano. Wycena przeliczy się w tle.";
const SPREAD_RANGE = "Podaj spread od 0 do 5 %.";

function symbolLine(instrument: Instrument): string {
  const symbol = instrument.price_symbol
    ? `Yahoo: ${instrument.price_symbol}${instrument.price_symbol_overridden ? " (ręczny)" : ""}`
    : "Brak symbolu w Yahoo";
  const spread = instrument.spread_pct ? ` · spread ${formatDecimal(instrument.spread_pct, 4)} %` : "";
  if (instrument.price_error) return symbol + spread;
  return (instrument.last_price_date ? `${symbol} · ostatnia cena ${formatDate(instrument.last_price_date)}` : `${symbol} · jeszcze bez cen`) + spread;
}

function symbolError(error: unknown): string {
  return error instanceof ApiError && error.code === "validation_error"
    ? "Symbol może zawierać litery, cyfry i znaki . - ^ =."
    : errorMessage(error);
}

function SpreadForm({ instrument }: { instrument: Instrument }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState(instrument.spread_pct ? formatDecimal(instrument.spread_pct, 4) : "");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (value: string | null) => api.updateInstrument(instrument.id, { spread_pct: value }),
    onSuccess: async () => {
      setError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.instruments }),
        queryClient.invalidateQueries({ queryKey: keys.portfolio }),
      ]);
    },
    onError: (err) => setError(errorMessage(err)),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) {
      save.mutate(null);
      return;
    }
    const value = parseAmount(text, 4);
    if (value === null || Number(value) > 5) {
      setError(SPREAD_RANGE);
      return;
    }
    save.mutate(value);
  }

  return (
    <form className={styles.sourceEdit} onSubmit={submit} noValidate>
      <Field id={`spread-${instrument.id}`} label="Spread (%)" error={error ?? undefined}
        hint="Połowa różnicy między ceną kupna a sprzedaży. Zostaw puste dla płynnych ETF-ów.">
        <input id={`spread-${instrument.id}`} inputMode="decimal" value={text}
          onChange={(e) => { setText(e.target.value); setError(null); save.reset(); }} aria-invalid={Boolean(error)} />
      </Field>
      {save.isSuccess && <p role="status">{SPREAD_SAVED}</p>}
      <div className={forms.actions}>
        <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Zapisz spread</button>
      </div>
    </form>
  );
}

function Source({ instrument, open, onToggle }: { instrument: Instrument; open: boolean; onToggle: () => void }) {
  const queryClient = useQueryClient();
  const [symbol, setSymbol] = useState(instrument.price_symbol ?? "");
  const [error, setError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (value: string | null) => api.updateInstrument(instrument.id, { price_symbol: value }),
    onSuccess: async (result) => {
      setError(null);
      setSymbol(result.price_symbol ?? "");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.instruments }),
        queryClient.invalidateQueries({ queryKey: keys.portfolio }),
      ]);
    },
    onError: (err) => setError(symbolError(err)),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!symbol.trim()) {
      setError("Podaj symbol, np. EIMI.L.");
      return;
    }
    save.mutate(symbol.trim());
  }

  const problem = hasPriceProblem(instrument);
  return (
    <li className={styles.source}>
      <button type="button" className={styles.sourceHead} aria-expanded={open} onClick={onToggle}>
        <span>
          <b>{instrument.xtb_ticker}</b>
          <small>{instrument.name}</small>
          <small>{symbolLine(instrument)}</small>
          {instrument.price_error && <small className={styles.problem}>{instrument.price_error}</small>}
        </span>
        <span className={problem ? styles.problem : "dim"}>{problem ? "wymaga uwagi" : "ok"}</span>
      </button>
      {open && (
        <>
        <form className={styles.sourceEdit} onSubmit={submit} noValidate>
          <Field id={`symbol-${instrument.id}`} label="Symbol w Yahoo" error={error ?? undefined}
            hint="Np. EIMI.L dla Londynu, SXR8.DE dla Xetry, VIE.PA dla Paryża.">
            <input id={`symbol-${instrument.id}`} value={symbol} onChange={(e) => { setSymbol(e.target.value); setError(null); save.reset(); }}
              aria-invalid={Boolean(error)} autoCapitalize="characters" />
          </Field>
          {save.isSuccess && <p role="status">{SAVED}</p>}
          <div className={forms.actions}>
            <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Zapisz symbol</button>
            {instrument.price_symbol_overridden && (
              <button type="button" className={ui.secondary} disabled={save.isPending} onClick={() => save.mutate(null)}>
                Przywróć automatyczny
              </button>
            )}
          </div>
        </form>
        <SpreadForm instrument={instrument} />
        </>
      )}
    </li>
  );
}

export function PriceSourcesScreen() {
  const instruments = useQuery({ queryKey: keys.instruments, queryFn: api.instruments });
  const [open, setOpen] = useState<number | null>(null);

  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <div>
        <h1 className={ui.pageTitle}>Źródła cen</h1>
        <p className="dim">Ceny pobieramy z Yahoo. Gdy symbol nie trafia, pozycja jest wyceniana ostatnią ceną z XTB.</p>
      </div>
      {instruments.isPending ? <Skeleton rows={4} />
        : instruments.isError ? <ErrorState error={instruments.error} onRetry={() => void instruments.refetch()} />
        : instruments.data.length === 0 ? <EmptyState title="Nie masz jeszcze instrumentów." />
        : (
          <ul className={styles.sources}>
            {problemsFirst(instruments.data).map((instrument) => (
              <Source key={instrument.id} instrument={instrument} open={open === instrument.id}
                onToggle={() => setOpen(open === instrument.id ? null : instrument.id)} />
            ))}
          </ul>
        )}
    </div>
  );
}
