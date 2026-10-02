import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Analytics, AnalyticsPeriod, DayExtreme } from "../../api/types";
import { DrawdownChart } from "../../charts/DrawdownChart";
import { formatDate, formatDecimal, formatMoney, formatPercent, signOf } from "../../format";
import { AccountSelect } from "../../ui/AccountPicker";
import { Money } from "../../ui/Amount";
import { Segmented } from "../../ui/Segmented";
import { HELP } from "../../ui/help";
import { InfoTip } from "../../ui/InfoTip";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { RECALC_POLL_MS } from "../dashboard/model";
import styles from "./Analysis.module.css";
import { MonthlyReturns } from "./MonthlyReturns";
import { PERIODS, shownReturn } from "./model";
import { SimulatorCard } from "../simulator/SimulatorCard";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");
const TOO_LITTLE = "za mało danych";

function Tile({ title, value, caption }: { title: string; value: ReactNode; caption: string }) {
  return (
    <div className={styles.tile} role="group" aria-label={title}>
      <div className={styles.tileHead}>
        <span>{title}</span>
        <InfoTip label={title} help={HELP[title]!} />
      </div>
      <div className={styles.value}>{value}</div>
      <div className={styles.caption}>{caption}</div>
    </div>
  );
}

const percent = (value: string | null, sign = true) => (
  <span className={`num ${sign ? tone(value) : ""}`}>{formatPercent(value, { places: 1, sign })}</span>
);

function dayCaption(day: DayExtreme | null): string {
  return day ? `${formatMoney(day.pln, { sign: true })} · ${formatDate(day.date)}` : TOO_LITTLE;
}

function drawdownCaption(data: Analytics): string {
  const fall = data.max_drawdown;
  if (!fall) return TOO_LITTLE;
  if (signOf(fall.pct) === 0) return "bez spadku od rekordu";
  const back = fall.recovered_on ? `odrobione ${formatDate(fall.recovered_on)}` : "nieodrobione";
  return `${formatDate(fall.peak_date)} → ${formatDate(fall.trough_date)} · ${back}`;
}

function Tiles({ data }: { data: Analytics }) {
  const annualized = data.period!.annualized;
  const twr = shownReturn(data.twr, annualized);
  const xirr = shownReturn(data.xirr, annualized);
  const risk = data.short_sample ? "rocznie · orientacyjnie" : "rocznie";
  return (
    <div className={styles.tiles}>
      <Tile title="Zysk" value={<Money value={data.profit_pln} sign tone />} caption="za okres" />
      <Tile title="TWR" value={percent(twr.value)} caption={twr.caption} />
      <Tile title="XIRR" value={percent(xirr.value)} caption={xirr.caption} />
      <Tile title="Maks. obsunięcie" value={percent(data.max_drawdown?.pct ?? null)} caption={drawdownCaption(data)} />
      <Tile title="Obecne obsunięcie" value={percent(data.current_drawdown_pct)} caption="od najwyższego poziomu" />
      <Tile title="Zmienność" value={percent(data.volatility_pct, false)} caption={data.volatility_pct === null ? TOO_LITTLE : risk} />
      <Tile title="Sharpe" value={<span className="num">{data.sharpe === null ? "—" : formatDecimal(data.sharpe, 2)}</span>}
        caption={data.sharpe === null ? TOO_LITTLE : risk} />
      <Tile title="Najlepszy dzień" value={percent(data.best_day?.pct ?? null)} caption={dayCaption(data.best_day)} />
      <Tile title="Najgorszy dzień" value={percent(data.worst_day?.pct ?? null)} caption={dayCaption(data.worst_day)} />
    </div>
  );
}

export function AnalysisScreen() {
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  const [period, setPeriod] = useState<AnalyticsPeriod>("all");
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const analytics = useQuery({
    queryKey: keys.analytics(accountIds, period),
    queryFn: () => api.analytics(accountIds, period),
    enabled: ready,
    placeholderData: (previous) => previous,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
  });

  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Analiza</h1>
      {accounts.data && <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />}
      <Segmented label="Okres" options={PERIODS} value={period} onChange={setPeriod} className={styles.periods} />
      {analytics.isPending ? <Skeleton rows={4} />
        : analytics.isError ? <ErrorState error={analytics.error} onRetry={() => void analytics.refetch()} />
        : analytics.data.period === null ? <EmptyState title="Nie ma jeszcze wyceny do pokazania." />
        : (
          <>
            {analytics.data.recalculating && <Recalculating />}
            <Tiles data={analytics.data} />
            <section className={ui.section} aria-labelledby="drawdown-title">
              <div className={ui.titleRow}>
                <h2 id="drawdown-title" className={ui.sectionTitle}>Obsunięcie w czasie</h2>
                <InfoTip label="Obsunięcie w czasie" help={HELP["Obsunięcie w czasie"]!} />
              </div>
              <DrawdownChart points={analytics.data.drawdown_series} />
            </section>
            <section className={ui.section} aria-labelledby="monthly-title">
              <div className={ui.titleRow}>
                <h2 id="monthly-title" className={ui.sectionTitle}>Zwrot w miesiącach</h2>
                <InfoTip label="Zwrot w miesiącach" help={HELP["Zwrot w miesiącach"]!} />
              </div>
              <MonthlyReturns rows={analytics.data.monthly} />
            </section>
          </>
        )}
      <SimulatorCard />
    </div>
  );
}
