/** Plan 9: tiles with a chart or a list — the value over time, one holding's price, allocation, today's movers. */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Summary } from "../../api/types";
import { ValueChart } from "../../charts/ValueChart";
import { windowForRange, type ChartWindow, type YRange } from "../../charts/viewport";
import { formatPercent, signOf } from "../../format";
import { PriceChartBody } from "../../screens/positions/PriceSection";
import { firstBuy } from "../../screens/positions/priceModel";
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
import type { Tile } from "../layout";
import { TileError, TileNote, TileSection } from "../parts";

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
  function resetChart() {
    setZoom(null);
    setYRange(null);
  }
  // Another account selection brings another history; a zoom into the old one means nothing there.
  const selectionKey = accountIds.join(",");
  useEffect(resetChart, [selectionKey]);
  return (
    <section className={styles.tileSection} aria-label="Wartość w czasie">
      {history.isPending ? <Skeleton chart rows={0} />
        : history.isError ? <TileError onRetry={() => void history.refetch()} />
          : <ValueChart points={history.data.points} view={zoom ?? rangeView} yRange={yRange}
            onViewChange={setZoom} onYRangeChange={setYRange} onReset={resetChart} />}
      <Segmented label="Zakres wykresu" options={RANGES} value={zoom ? null : range}
        onChange={(next) => { setRange(next); resetChart(); }} />
    </section>
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
  return (
    <TileSection title={name} more={{ to: `/pozycje/${accountId}/${instrumentId}`, label: `Szczegóły ${name}` }}>
      <span className="dim">{`${position.ticker ?? ""} · ${position.account_name}`}</span>
      {detail.isPending ? <Skeleton rows={3} /> : (
        <PriceChartBody accountId={accountId} instrumentId={instrumentId} initialRange={range}
          average={detail.data && signOf(detail.data.position.quantity) > 0 ? detail.data.average_price : null}
          firstBuy={detail.data ? firstBuy(detail.data) : null} />
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
  const small = tile.size === "S";
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
          <div>
            {rows.map((row) => (
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
  const movers = positions.data ? dayMovers(positions.data, tile.settings.count) : [];
  return (
    <TileSection title="Dziś najbardziej" more={{ to: "/pozycje", label: "Wszystkie pozycje", text: "Wszystkie pozycje" }}>
      {positions.isPending ? <Skeleton rows={3} />
        : positions.isError ? <TileError onRetry={() => void positions.refetch()} />
          : movers.length === 0 ? <TileNote>Dziś bez zmian.</TileNote> : (
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
          )}
    </TileSection>
  );
}
