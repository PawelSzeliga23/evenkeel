import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { IncomeCost, IncomePeriod, IncomeSource } from "../../api/types";
import { formatMoney, signOf } from "../../format";
import { AccountSelect } from "../../ui/AccountPicker";
import { Money } from "../../ui/Amount";
import { BackLink } from "../../ui/BackLink";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import tiles from "../analysis/Analysis.module.css";
import { RECALC_POLL_MS } from "../dashboard/model";
import styles from "./Income.module.css";
import { IncomeChart, PARTS } from "./IncomeChart";
import { PERIODS, buckets, type Bucket } from "./model";

const money = (value: number) => formatMoney(value.toFixed(2), { sign: true });
const minus = (value: string) => (signOf(value) > 0 ? `-${value}` : value);

function Tile({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={tiles.tile} role="group" aria-label={title}>
      <div className={tiles.tileHead}><span>{title}</span></div>
      <div className={tiles.value}>{children}</div>
    </div>
  );
}

function sourceNote(source: IncomeSource): string {
  if (source.kind === "dividend") return `brutto ${formatMoney(source.gross_pln)} − podatek u źródła ${formatMoney(source.tax_pln)}`;
  const what = source.kind === "bond" || source.kind === "savings" ? "odsetki naliczone" : "odsetki";
  if (!source.taxed) return `${what} · w IKE/IKZE bez podatku`;
  return `brutto ${formatMoney(source.gross_pln)} − Belka ${formatMoney(source.tax_pln)}`;
}

const COST_NOTES: Record<IncomeCost["key"], (cost: IncomeCost) => string> = {
  fx: (cost) => `0,5 % przy zakupach i sprzedaży w obcej walucie · ${cost.count} transakcji`,
  interest_tax: () => "19 % od odsetek poza IKE/IKZE",
  withholding_tax: () => "od dywidend",
  fees: (cost) => (signOf(cost.amount_pln) > 0 ? `${cost.count} transakcji` : "XTB: 0 % do 100 tys. € obrotu"),
};

function Details({ bucket }: { bucket: Bucket }) {
  const parts = [...PARTS.income.map((p) => [p.label, bucket[p.key]] as const),
    ...PARTS.costs.map((p) => [p.label, -bucket[p.key]] as const)].filter(([, value]) => value !== 0);
  return (
    <section className={styles.details} aria-label={bucket.title}>
      <b>{bucket.title}</b>
      <div>dochód {money(bucket.income)} · koszty {money(-bucket.costs)} · bilans {money(bucket.balance)}</div>
      <div className="dim">{parts.map(([label, value]) => `${label} ${money(value)}`).join(" · ")}</div>
    </section>
  );
}

/** Analiza → Dochód i koszty: passive income against costs, month by month. */
export function IncomeScreen() {
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  const [period, setPeriod] = useState<IncomePeriod>("ytd");
  const [selected, setSelected] = useState<string | null>(null);
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const report = useQuery({
    queryKey: keys.income(accountIds, period),
    queryFn: () => api.income(accountIds, period),
    enabled: ready,
    placeholderData: (previous) => previous,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
  });
  const data = report.data;
  const bars = data ? buckets(data.months) : [];
  const picked = bars.find((b) => b.key === selected);
  const years = bars.length > 0 && bars[0]!.key.length === 4;
  const hasDividends = data?.sources.some((s) => s.kind === "dividend");

  return (
    <div className={ui.page}>
      <BackLink to="/analiza" label="Analiza" />
      <h1 className={ui.pageTitle}>Dochód i koszty</h1>
      {accounts.data && <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />}
      <Segmented label="Okres" options={PERIODS} value={period} onChange={(value) => { setPeriod(value); setSelected(null); }} />
      {report.isPending ? <Skeleton rows={4} />
        : report.isError ? <ErrorState error={report.error} onRetry={() => void report.refetch()} />
        : data!.period === null ? <EmptyState title="Nie ma jeszcze danych do pokazania." />
        : (
          <div className={report.isPlaceholderData ? `${styles.body} ${styles.stale}` : styles.body} aria-busy={report.isPlaceholderData}>
            {data!.recalculating && <Recalculating />}
            <div className={styles.tiles}>
              <Tile title="Dochód"><Money value={data!.totals.income_pln} sign tone /></Tile>
              <Tile title="Koszty"><Money value={minus(data!.totals.costs_pln)} sign tone /></Tile>
              <Tile title="Bilans"><Money value={data!.totals.balance_pln} sign tone /></Tile>
            </div>
            <section className={ui.section} aria-labelledby="months-chart-title">
              <h2 id="months-chart-title" className={ui.sectionTitle}>{years ? "Rok po roku" : "Miesiąc po miesiącu"}</h2>
              <IncomeChart buckets={bars} selected={picked ? selected : null} onSelect={(key) => setSelected(key === selected ? null : key)} />
              <ul className={styles.legend}>
                {[...PARTS.income, ...PARTS.costs].map((part) => <li key={part.key}><i style={{ background: part.color }} />{part.label}</li>)}
              </ul>
              {picked ? <Details bucket={picked} /> : <p className={styles.hint}>Nad kreską dochód, pod kreską koszty. Dotknij słupka, żeby zobaczyć szczegóły.</p>}
            </section>
            <section className={ui.section}>
              <h2 className={ui.sectionTitle}>Skąd dochód</h2>
              <ul className={styles.list} aria-label="Skąd dochód">
                {data!.sources.map((source) => (
                  <li key={source.key} className={ui.row}>
                    <span className={ui.rowName}><b>{source.name}</b><small>{sourceNote(source)}</small></span>
                    <span className={ui.rowAmount}><Money value={source.net_pln} sign tone /></span>
                  </li>
                ))}
                {!hasDividends && (
                  <li className={ui.row}>
                    <span className={ui.rowName}><b>Dywidendy</b><small>na razie brak</small></span>
                    <span className={`${ui.rowAmount} dim`}>{formatMoney("0")}</span>
                  </li>
                )}
              </ul>
            </section>
            <section className={ui.section}>
              <h2 className={ui.sectionTitle}>Na co koszty</h2>
              <ul className={styles.list} aria-label="Na co koszty">
                {data!.costs.map((cost) => (
                  <li key={cost.key} className={ui.row}>
                    <span className={ui.rowName}><b>{cost.name}</b><small>{COST_NOTES[cost.key](cost)}</small></span>
                    <span className={ui.rowAmount}><Money value={minus(cost.amount_pln)} sign tone /></span>
                  </li>
                ))}
              </ul>
            </section>
            <section className={ui.section}>
              <h2 className={ui.sectionTitle}>Miesiące</h2>
              <table className={styles.table} aria-label="Miesiące">
                <thead><tr><th>{years ? "Rok" : "Miesiąc"}</th><th>Dochód</th><th>Koszty</th><th>Bilans</th></tr></thead>
                <tbody>
                  {[...bars].reverse().map((b) => (
                    <tr key={b.key}>
                      <td>{b.title}</td>
                      <td className={`num ${b.income > 0 ? "up" : ""}`}>{money(b.income)}</td>
                      <td className={`num ${b.costs > 0 ? "down" : ""}`}>{money(-b.costs)}</td>
                      <td className={`num ${b.balance > 0 ? "up" : b.balance < 0 ? "down" : ""}`}>{money(b.balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>
        )}
    </div>
  );
}
