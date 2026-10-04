/** Plan 9: tiles with a chart or a list — the value over time, one holding's price, allocation, today's movers. */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { HistoryPoint, Summary } from "../../api/types";
import { ValueChart } from "../../charts/ValueChart";
import { windowForRange, type ChartWindow, type YRange } from "../../charts/viewport";
import { formatPercent, signOf, todayIso } from "../../format";
import { PriceChartBody } from "../../screens/positions/PriceSection";
import { firstBuy, formatPrice, rangeFrom as priceFrom } from "../../screens/positions/priceModel";
import {
  ALLOCATION_MODES, RANGES, allocationRows, dayMovers, rangeFrom, type AllocationMode, type Range,
} from "../../screens/dashboard/model";
import base from "../../screens/dashboard/Dashboard.module.css";
import { Money } from "../../ui/Amount";
import { ListRow } from "../../ui/ListRow";
import { Segmented } from "../../ui/Segmented";
import { Skeleton } from "../../ui/States";
import { shortTicker } from "../../ui/ticker";
import styles from "../Dashboard.module.css";
import { widthOf, type Tile } from "../layout";
import { Sparkline, TileBrief, TileError, TileNote, TileSection } from "../parts";

const RANGE_NAMES: Record<Range, string> = { "1M": "1 miesiąc", "3M": "3 miesiące", "1R": "1 rok", ALL: "cały okres" };

/** The time-weighted return between two days of the history (deposits do not count as gains), as "5.20"; null without TWR. */
function rangeReturn(first: HistoryPoint | undefined, last: HistoryPoint | undefined): string | null {
  if (!first || !last || first.twr_pct === null || last.twr_pct === null) return null;
  return (((1 + Number(last.twr_pct) / 100) / (1 + Number(first.twr_pct) / 100) - 1) * 100).toFixed(2);
}

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

export function ValueChartTile({ tile, summary }: { tile: Tile<"value_chart">; summary: Summary }) {
  const [accountIds, , ready] = useAccountSelection();
  const [range, setRange] = useState<Range>(tile.settings.range);
  const [zoom, setZoom] = useState<ChartWindow | null>(null);
  const [yRange, setYRange] = useState<YRange | null>(null);
  const history = useQuery({
    queryKey: keys.history(accountIds, null), queryFn: () => api.history(accountIds, null),
    enabled: ready && summary.as_of !== null, placeholderData: (previous) => previous,
  });
  const dates = useMemo(() => (history.data?.points ?? []).map((p) => p.date), [history.data]);
  const rangeView = windowForRange(dates, rangeFrom(range, dates[dates.length - 1] ?? null));
  const small = tile.variant === "S2";
  function resetChart() {
    setZoom(null);
    setYRange(null);
  }
  // Another account selection brings another history; a zoom into the old one means nothing there.
  const selectionKey = accountIds.join(",");
  useEffect(resetChart, [selectionKey]);
  if (small) {
    const points = history.data?.points ?? [];
    const shown = points.slice(Math.max(0, Math.ceil(rangeView.from - 1e-9)));
    const moved = rangeReturn(shown[0], shown[shown.length - 1]);
    return (
      <TileBrief title="Wykres wartości" value={<Money value={summary.value_pln} />}
        note={moved === null ? RANGE_NAMES[range] : <><span className={`num ${tone(moved)}`}>{formatPercent(moved)}</span> TWR · {RANGE_NAMES[range]}</>}>
        {history.isError ? <TileError onRetry={() => void history.refetch()} />
          : <Sparkline values={shown.map((p) => Number(p.value_pln))} label={`Wartość portfela, ${RANGE_NAMES[range]}`} />}
      </TileBrief>
    );
  }
  return (
    <section className={styles.tileSection} aria-label="Wartość w czasie">
      {history.isPending ? <Skeleton chart rows={0} />
        : history.isError ? <TileError onRetry={() => void history.refetch()} />
          : <ValueChart points={history.data.points} view={zoom ?? rangeView} yRange={yRange}
            maxHeight={tile.variant === "L6" ? 300 : 190}
            onViewChange={setZoom} onYRangeChange={setYRange} onReset={resetChart} />}
      <Segmented label="Zakres wykresu" options={RANGES} value={zoom ? null : range}
        onChange={(next) => { setRange(next); resetChart(); }} />
    </section>
  );
}

/** A small price tile: the last price, the change since the first purchase and a line of the prices since then. */
function PriceBrief({ accountId, instrumentId, name, bought }: {
  accountId: number; instrumentId: number; name: string; bought: string | null;
}) {
  const from = priceFrom("buy", bought, todayIso());
  const prices = useQuery({
    queryKey: keys.positionPrices(accountId, instrumentId, from),
    queryFn: () => api.positionPrices(accountId, instrumentId, from),
  });
  const data = prices.data;
  const last = data?.points[data.points.length - 1];
  const buy = data?.markers.find((m) => m.kind === "buy" && m.price !== null);
  const moved = last && buy ? (((Number(last.close) - Number(buy.price)) / Number(buy.price)) * 100).toFixed(2) : null;
  return (
    <TileBrief title={name} to={`/pozycje/${accountId}/${instrumentId}`}
      value={last ? <span className="num">{formatPrice(last.close, data!.currency)}</span> : <span className="num dim">—</span>}
      note={moved === null ? undefined : <><span className={`num ${tone(moved)}`}>{formatPercent(moved)}</span> od 1. zakupu</>}>
      {prices.isError ? <TileError onRetry={() => void prices.refetch()} />
        : data && <Sparkline values={data.points.map((p) => Number(p.close))} label={`Cena ${name} od zakupu`} />}
    </TileBrief>
  );
}

export function PriceChartTile({ tile }: { tile: Tile<"price_chart"> }) {
  const [accountIds, , ready] = useAccountSelection();
  const { account_id: accountId, instrument_id: instrumentId, range } = tile.settings;
  const positions = useQuery({
    queryKey: keys.positions(accountIds), queryFn: () => api.positions(accountIds), enabled: ready,
    placeholderData: (previous) => previous,
  });
  const position = positions.data?.find((p) => p.account_id === accountId && p.instrument_id === instrumentId);
  const detail = useQuery({
    queryKey: keys.position(accountId ?? 0, instrumentId ?? 0), queryFn: () => api.position(accountId!, instrumentId!),
    enabled: position !== undefined,
  });
  if (accountId === null || instrumentId === null) {
    return <TileSection title="Wykres ceny"><TileNote>Wybierz walor w ustawieniach kafelka.</TileNote></TileSection>;
  }
  if (positions.isPending) return <TileSection title="Wykres ceny"><Skeleton rows={3} /></TileSection>;
  if (positions.isError) {
    return <TileSection title="Wykres ceny"><TileError onRetry={() => void positions.refetch()} /></TileSection>;
  }
  if (position === undefined) {
    return (
      <TileSection title="Wykres ceny">
        <TileNote>Tego waloru nie ma już w portfelu — wybierz inny w ustawieniach kafelka.</TileNote>
      </TileSection>
    );
  }
  const name = position.name;
  if (tile.variant === "S2") {
    return detail.isPending ? <TileSection title={name}><Skeleton rows={2} /></TileSection>
      : <PriceBrief accountId={accountId} instrumentId={instrumentId} name={name} bought={detail.data ? firstBuy(detail.data) : null} />;
  }
  return (
    <TileSection title={name} more={{ to: `/pozycje/${accountId}/${instrumentId}`, label: `Szczegóły ${name}` }}>
      <span className="dim">{`${position.ticker ?? ""} · ${position.account_name}`}</span>
      {detail.isPending ? <Skeleton rows={3} /> : (
        <PriceChartBody accountId={accountId} instrumentId={instrumentId} initialRange={range}
          average={detail.data && signOf(detail.data.position.quantity) > 0 ? detail.data.average_price : null}
          firstBuy={detail.data ? firstBuy(detail.data) : null}
          compact={tile.variant === "M5"} maxHeight={tile.variant === "M5" ? 230 : 300} />
      )}
    </TileSection>
  );
}

export function AllocationTile({ tile, summary }: { tile: Tile<"allocation">; summary: Summary }) {
  const [accountIds, , ready] = useAccountSelection();
  const [mode, setMode] = useState<AllocationMode>(tile.settings.by);
  const asOf = summary.as_of;
  const exposure = useQuery({
    queryKey: keys.exposure(accountIds, asOf ?? ""), queryFn: () => api.exposure(accountIds, asOf!),
    enabled: ready && asOf !== null && mode === "currency",
  });
  const rows = allocationRows(mode, summary, exposure.data);
  const small = tile.variant === "S2";
  const wide = widthOf(tile.variant) === "L";
  const bar = (
    <div className={base.allocBar} aria-hidden="true">
      {rows.map((row) => <i key={row.key} style={{ flex: Math.max(Number(row.value), 0), background: row.color }} />)}
    </div>
  );
  const body = mode === "currency" && exposure.isPending ? <Skeleton rows={2} />
    : mode === "currency" && exposure.isError ? <TileError onRetry={() => void exposure.refetch()} />
      : small ? (
        <>
          {bar}
          {rows[0] && (
            <div className={styles.tileAllocTop}>
              <span>{rows[0].name}</span>
              <span className="num dim">{formatPercent(rows[0].share, { sign: false, places: 1 })}</span>
            </div>
          )}
        </>
      ) : (
        <>
          {bar}
          <div className={styles.tileRows} data-cols={wide ? 2 : 1}>
            {(wide ? rows : rows.slice(0, 5)).map((row) => (
              <div key={row.key} className={base.allocRow}>
                <span className={base.dot} style={{ background: row.color }} />
                <span>{row.name}</span>
                <span className={base.allocAmount}>
                  <Money value={row.value} />
                  <small className="num dim">{formatPercent(row.share, { sign: false, places: 1 })}</small>
                </span>
              </div>
            ))}
          </div>
        </>
      );
  return (
    <TileSection title="Alokacja" more={mode === "currency" && !small ? { to: "/ekspozycja", label: "Zobacz w czasie", text: "Zobacz w czasie" } : undefined}>
      {!small && <Segmented label="Alokacja według" options={ALLOCATION_MODES} value={mode} onChange={setMode} />}
      {body}
    </TileSection>
  );
}

export function MoversTile({ tile, summary }: { tile: Tile<"movers">; summary: Summary }) {
  const [accountIds, , ready] = useAccountSelection();
  const positions = useQuery({
    queryKey: keys.positions(accountIds), queryFn: () => api.positions(accountIds),
    enabled: ready && summary.as_of !== null, placeholderData: (previous) => previous,
  });
  const small = tile.variant === "S2";
  const movers = positions.data ? dayMovers(positions.data, small ? Number.MAX_SAFE_INTEGER : tile.settings.count) : [];
  if (small) {
    const up = movers.filter((m) => signOf(m.pct) > 0).sort((a, b) => Number(b.pct) - Number(a.pct))[0];
    const down = movers.filter((m) => signOf(m.pct) < 0).sort((a, b) => Number(a.pct) - Number(b.pct))[0];
    return (
      <TileBrief title="Dziś najbardziej" to="/pozycje" value={positions.isError ? <TileError onRetry={() => void positions.refetch()} />
        : movers.length === 0 ? <span className="dim">{positions.isPending ? "…" : "Dziś bez zmian."}</span> : (
          <span className={styles.tileBriefPair}>
            {[up, down].filter((m) => m !== undefined).map(({ position, pct }) => (
              <span key={`${position.account_id}-${position.instrument_id}`}>
                <span>{shortTicker(position.ticker ?? position.name)}</span>
                <span className={`num ${tone(pct)}`}>{formatPercent(pct)}</span>
              </span>
            ))}
          </span>
        )} />
    );
  }
  return (
    <TileSection title="Dziś najbardziej" more={{ to: "/pozycje", label: "Wszystkie pozycje", text: "Wszystkie pozycje" }}>
      {positions.isPending ? <Skeleton rows={3} />
        : positions.isError ? <TileError onRetry={() => void positions.refetch()} />
          : movers.length === 0 ? <TileNote>Dziś bez zmian.</TileNote> : (
            <div className={styles.tileRows} data-cols={widthOf(tile.variant) === "L" ? 2 : 1}>
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
          )}
    </TileSection>
  );
}
