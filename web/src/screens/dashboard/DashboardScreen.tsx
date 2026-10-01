import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Summary } from "../../api/types";
import { ValueChart } from "../../charts/ValueChart";
import { windowForRange, type ChartWindow, type YRange } from "../../charts/viewport";
import { formatDayLong, formatMoney, formatRefreshed, formatPercent, pluralPl, signOf, sumMoney } from "../../format";
import { RefreshIcon } from "../../shell/icons";
import { AccountSelect } from "../../ui/AccountPicker";
import { HeroAmount, Money } from "../../ui/Amount";
import { AnalyticsCard } from "../analysis/AnalyticsCard";
import { LimitsCard } from "../limits/LimitsCard";
import { HELP } from "../../ui/help";
import { InfoTip } from "../../ui/InfoTip";
import { ListRow } from "../../ui/ListRow";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import { shortTicker } from "../../ui/ticker";
import ui from "../../ui/ui.module.css";
import styles from "./Dashboard.module.css";
import {
  ALLOCATION_MODES, RANGES, RECALC_POLL_MS, allocationRows, dayMovers, rangeFrom, type AllocationMode, type Range,
} from "./model";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

export function DashboardScreen() {
  const queryClient = useQueryClient();
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  const [range, setRange] = useState<Range>("1R");
  const [mode, setMode] = useState<AllocationMode>("kind");
  const [zoom, setZoom] = useState<ChartWindow | null>(null);
  const [yRange, setYRange] = useState<YRange | null>(null);

  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const summary = useQuery({
    queryKey: keys.summary(accountIds),
    queryFn: () => api.summary(accountIds),
    enabled: ready,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
    placeholderData: (previous) => previous,
  });
  const asOf = summary.data?.as_of ?? null;
  const history = useQuery({ queryKey: keys.history(accountIds, null), queryFn: () => api.history(accountIds, null), enabled: ready && asOf !== null, placeholderData: (previous) => previous });
  const dates = useMemo(() => (history.data?.points ?? []).map((p) => p.date), [history.data]);
  const rangeView = windowForRange(dates, rangeFrom(range, dates[dates.length - 1] ?? null));
  // Another account selection brings another history; a zoom into the old one means nothing there.
  const selectionKey = accountIds.join(",");
  function resetChart() {
    setZoom(null);
    setYRange(null);
  }
  useEffect(resetChart, [selectionKey]);
  const exposure = useQuery({
    queryKey: keys.exposure(accountIds, asOf ?? ""),
    queryFn: () => api.exposure(accountIds, asOf!),
    enabled: ready && asOf !== null && mode === "currency",
  });
  const positions = useQuery({ queryKey: keys.positions(accountIds), queryFn: () => api.positions(accountIds), enabled: ready && asOf !== null, placeholderData: (previous) => previous });

  // When the background recalculation ends, everything valued may have changed.
  const recalculating = summary.data?.recalculating ?? false;
  const wasRecalculating = useRef(false);
  useEffect(() => {
    if (wasRecalculating.current && !recalculating) {
      void queryClient.invalidateQueries({ queryKey: keys.portfolio, predicate: (q) => q.queryKey[1] !== "summary" });
    }
    wasRecalculating.current = recalculating;
  }, [recalculating, queryClient]);

  // Fetch current prices now; the summary then reports the recalculation and the rest follows as above.
  const refresh = useMutation({
    mutationFn: api.refreshPrices,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.portfolio }),
  });
  const refreshedAt = summary.data?.prices_refreshed_at ?? null;

  const header = (
    <>
      <div className={styles.bar}>
        {accounts.data ? <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} /> : <span />}
        {refreshedAt ? (
          <span className={styles.refreshed}>
            <span className="dim">{formatRefreshed(refreshedAt)}</span>
            <button type="button" className={styles.refresh} aria-label="Odśwież ceny" disabled={refresh.isPending}
              data-spinning={refresh.isPending || recalculating} onClick={() => refresh.mutate()}>
              <RefreshIcon />
            </button>
          </span>
        ) : asOf && <span className="dim">{formatDayLong(asOf)}</span>}
      </div>
      {refresh.isError && <p role="alert" className={styles.refreshError}>Nie udało się odświeżyć cen. Spróbuj ponownie.</p>}
    </>
  );

  if (summary.isPending) return <div className={ui.page}>{header}<Skeleton chart rows={4} /></div>;
  if (summary.isError) return <div className={ui.page}>{header}<ErrorState error={summary.error} onRetry={() => void summary.refetch()} /></div>;

  const data: Summary = summary.data;
  if (asOf === null) {
    return (
      <div className={ui.page}>
        {header}
        {recalculating ? <><Recalculating /><Skeleton chart rows={3} /></> : (
          <EmptyState
            title="Wgraj eksport z XTB, żeby zobaczyć swój portfel."
            action={<Link className={ui.primaryButton} to="/dodaj/xtb">Wgraj pliki z XTB</Link>}
          />
        )}
      </div>
    );
  }

  const rows = allocationRows(mode, data, exposure.data);
  const movers = positions.data ? dayMovers(positions.data) : [];
  const approximate = data.approximate_positions;

  return (
    <div className={ui.page}>
      {header}
      <section className={styles.hero} aria-label="Podsumowanie">
        <span className="dim">Wartość portfela</span>
        <HeroAmount value={data.value_pln} />
        {signOf(data.exit_cost_pln) > 0 && (
          <p className="dim num">
            {`Wartość rynkowa ${formatMoney(data.market_value_pln)} · koszty wyjścia ${formatMoney(`-${data.exit_cost_pln}`)}`}
          </p>
        )}
        {data.day_change_pln !== null && (
          <p className={styles.today}>
            <Money value={data.day_change_pln} sign tone />{" "}
            <span className={`num ${tone(data.day_change_pct)}`}>({formatPercent(data.day_change_pct)})</span>{" "}
            <span className="dim">dziś</span>
          </p>
        )}
        <dl className={styles.stats}>
          <div><dt><span>Zysk łącznie</span><InfoTip label="Zysk łącznie" help={HELP["Zysk łącznie"]!} /></dt><dd><Money value={data.total_gain_pln} sign tone /></dd></div>
          <div><dt><span>Stopa zwrotu (TWR)</span><InfoTip label="Stopa zwrotu (TWR)" help={HELP["Stopa zwrotu (TWR)"]!} /></dt><dd className={`num ${tone(data.twr_pct)}`}>{formatPercent(data.twr_pct, { places: 1 })}</dd></div>
          <div><dt><span>Wpłacono</span><InfoTip label="Wpłacono" help={HELP["Wpłacono"]!} /></dt><dd><Money value={data.invested_pln} /></dd></div>
          <div><dt><span>Dywidendy i odsetki</span><InfoTip label="Dywidendy i odsetki" help={HELP["Dywidendy i odsetki"]!} /></dt><dd><Money value={sumMoney([data.dividends_net_pln, data.interest_net_pln])} /></dd></div>
        </dl>
        {approximate > 0 && (
          <p className="flag">
            {approximate} {pluralPl(approximate, "pozycja wyceniona", "pozycje wycenione", "pozycji wycenionych")} w przybliżeniu
          </p>
        )}
        {recalculating && <Recalculating />}
      </section>

      <section className={ui.section} aria-label="Wartość w czasie">
        {history.isPending ? <Skeleton chart rows={0} />
          : history.isError ? <ErrorState error={history.error} onRetry={() => void history.refetch()} />
            : <ValueChart points={history.data.points} view={zoom ?? rangeView} yRange={yRange}
              onViewChange={setZoom} onYRangeChange={setYRange} onReset={resetChart} />}
        <Segmented label="Zakres wykresu" options={RANGES} value={zoom ? null : range}
          onChange={(next) => { setRange(next); resetChart(); }} />
      </section>

      <section className={ui.section} aria-labelledby="allocation-title">
        <div className={ui.sectionHead}>
          <h2 id="allocation-title" className={ui.sectionTitle}>Alokacja</h2>
          {mode === "currency" && <Link className={ui.sectionMore} to="/ekspozycja">Zobacz w czasie</Link>}
        </div>
        <Segmented label="Alokacja według" options={ALLOCATION_MODES} value={mode} onChange={setMode} />
        {mode === "currency" && exposure.isPending ? <Skeleton rows={2} />
          : mode === "currency" && exposure.isError ? <ErrorState error={exposure.error} onRetry={() => void exposure.refetch()} />
            : (
              <>
                <div className={styles.allocBar} aria-hidden="true">
                  {rows.map((row) => <i key={row.key} style={{ flex: Math.max(Number(row.value), 0), background: row.color }} />)}
                </div>
                <div>
                  {rows.map((row) => (
                    <div key={row.key} className={styles.allocRow}>
                      <span className={styles.dot} style={{ background: row.color }} />
                      <span>{row.name}</span>
                      <span className={styles.allocAmount}>
                        <Money value={row.value} />
                        <small className="num dim">{formatPercent(row.share, { sign: false, places: 1 })}</small>
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
      </section>

      <AnalyticsCard />

      <LimitsCard />

      {movers.length > 0 && (
        <section className={ui.section} aria-labelledby="movers-title">
          <div className={ui.sectionHead}>
            <h2 id="movers-title" className={ui.sectionTitle}>Dziś najbardziej</h2>
            <Link className={ui.sectionMore} to="/pozycje">Wszystkie pozycje</Link>
          </div>
          <div>
            {movers.map(({ position, pct }) => (
              <ListRow
                key={`${position.account_id}-${position.instrument_id}`}
                to={`/pozycje/${position.account_id}/${position.instrument_id}`}
                lead={shortTicker(position.ticker ?? position.name)}
                title={position.name}
                subtitle={position.account_name}
                value={<span className={`num ${tone(pct)}`}>{formatPercent(pct)}</span>}
                detail={<Money value={position.day_change_pln} sign />}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
