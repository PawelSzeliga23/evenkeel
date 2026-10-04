import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { IsoDate, Money, PriceChartData, PriceMarker } from "../../api/types";
import { MARKER_COLORS, PriceChart } from "../../charts/PriceChart";
import { clampWindow, fullWindow, type ChartWindow } from "../../charts/viewport";
import { formatDate, formatDecimal, formatMoney, formatPercent, signOf, todayIso } from "../../format";
import { ErrorState, Skeleton } from "../../ui/States";
import { Segmented } from "../../ui/Segmented";
import ui from "../../ui/ui.module.css";
import { PRICE_RANGES, chartMarks, formatPrice, rangeFrom, type NoteMark, type PriceRange } from "./priceModel";
import styles from "./Positions.module.css";
import { usePreferences } from "../../settings/preferences";

const TITLE_ID = "section-Wykres-ceny";
const KIND_NAMES: Record<PriceMarker["kind"], string> = { buy: "Zakup", sell: "Sprzedaż", dividend: "Dywidenda" };

/** The change from `base` to `last` in percent, as the API would write it ("29.01"); null without a base. */
function change(last: number, base: number | null): string | null {
  return base ? (((last - base) / base) * 100).toFixed(2) : null;
}

const tone = (value: string | null) => (value === null ? "" : signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

const NO_RATE = "kwota w zł po pobraniu kursu NBP";

function Operation({ marker, last, currency }: { marker: PriceMarker; last: number; currency: string | null }) {
  const head = `${KIND_NAMES[marker.kind]}, ${formatDate(marker.date)}`;
  if (marker.kind === "dividend") {
    return (
      <div className={styles.operation} role="status">
        <b>{head}</b>
        <span className="num up">{marker.amount_pln === null ? NO_RATE : formatMoney(marker.amount_pln, { sign: true })}</span>
      </div>
    );
  }
  const amount = marker.amount_pln === null ? NO_RATE : formatMoney(marker.amount_pln.replace(/^-/, ""));
  const lines = [
    [
      marker.quantity === null ? "" : `${formatDecimal(marker.quantity, 8)} szt.`,
      marker.price === null ? "" : `po ${formatPrice(marker.price, currency)}`,
    ].filter(Boolean).join(" "),
    `${marker.kind === "buy" ? "zapłacone" : "otrzymane"} ${amount}`,
  ].filter(Boolean).join(" · ");
  const since = change(last, marker.price === null ? null : Number(marker.price));
  return (
    <div className={styles.operation} role="status">
      <b>{head}</b>
      <span className="num">{lines}</span>
      {marker.price_with_fx !== null && (
        <span className="num dim">{`z przewalutowaniem XTB ${formatPrice(marker.price_with_fx, currency)}`}</span>
      )}
      {since !== null && <span className={`num ${tone(since)}`}>{`dziś ${formatPercent(since)}`}</span>}
    </div>
  );
}

function NoteDay({ mark }: { mark: NoteMark }) {
  return (
    <div className={styles.operation} role="status">
      <b>{`Notatki, ${formatDate(mark.date)}`}</b>
      {mark.entries.map((entry) => (
        <span key={entry.id} className={styles.noteLine}>
          <b style={{ color: MARKER_COLORS.note }} aria-hidden="true">N </b>
          {entry.entry_date !== mark.date && <span className="dim">{`(${formatDate(entry.entry_date)}) `}</span>}
          {entry.body}
        </span>
      ))}
    </div>
  );
}

function Legend({ average, notes }: { average: boolean; notes: boolean }) {
  const items: [string, string, string][] = [
    ["▲", "Zakup", MARKER_COLORS.buy], ["▼", "Sprzedaż", MARKER_COLORS.sell], ["D", "Dywidenda", MARKER_COLORS.dividend],
    ...(notes ? [["N", "Notatka", MARKER_COLORS.note] as [string, string, string]] : []),
  ];
  return (
    <p className={styles.legend}>
      {items.map(([mark, name, color]) => (
        <span key={name}><b style={{ color }} aria-hidden="true">{mark}</b> {name}</span>
      ))}
      {average && <span><i className={styles.averageSwatch} style={{ borderColor: MARKER_COLORS.average }} /> Średnia cena zakupu</span>}
    </p>
  );
}

function Chart({ data, average, sinceBuy }: { data: PriceChartData; average: Money | null; sinceBuy: boolean }) {
  const [zoom, setZoom] = useState<ChartWindow | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const count = data.points.length;
  const view = clampWindow(zoom ?? fullWindow(count), count);
  useEffect(() => { setZoom(null); setSelected(null); }, [data]);

  if (count < 2) return <p className="dim">Brak notowań dla tego instrumentu.</p>;

  const last = Number(data.points[count - 1]!.close);
  const firstBuy = data.markers.find((m) => m.kind === "buy" && m.price !== null);
  const fromBuy = sinceBuy && firstBuy !== undefined;
  const base = fromBuy ? Number(firstBuy.price) : Number(data.points[Math.ceil(view.from - 1e-9)]!.close);
  const moved = change(last, base);
  const marks = chartMarks(data);
  const marker = selected === null ? null : marks[selected] ?? null;

  return (
    <>
      <p className={styles.priceHead}>
        <b className="num">{formatPrice(data.points[count - 1]!.close, data.currency)}</b>
        {moved !== null && <span className={`num ${tone(moved)}`}>{`${formatPercent(moved)} ${fromBuy ? "od 1. zakupu" : "w zakresie"}`}</span>}
      </p>
      <PriceChart data={data} average={average} selected={selected} onSelect={setSelected}
        view={view} onViewChange={setZoom} onReset={() => setZoom(null)} />
      <Legend average={average !== null} notes={data.notes.length > 0} />
      {marker?.kind === "note" && (
        <>
          <NoteDay mark={marker} />
          {data.markers.filter((m) => m.date === marker.date).map((m, i) => (
            <Operation key={i} marker={m} last={last} currency={data.currency} />
          ))}
        </>
      )}
      {marker && marker.kind !== "note" && <Operation marker={marker} last={last} currency={data.currency} />}
      <p className={styles.hint}>Szczypnij lub przesuń, żeby zmienić zakres; dotknij znacznika, żeby zobaczyć operację.</p>
    </>
  );
}

/** Wykres ceny (spec 7e): the instrument's price in its currency with the position's operations on it. */
export function PriceSection({ accountId, instrumentId, average, firstBuy }: {
  accountId: number; instrumentId: number; average: Money | null;
  /** The position's first purchase (from its details), where „Od zakupu” starts. */
  firstBuy: IsoDate | null;
}) {
  const prefs = usePreferences();
  return (
    <section className={ui.section} aria-labelledby={TITLE_ID}>
      <h2 id={TITLE_ID} className={ui.sectionTitle}>Wykres ceny</h2>
      <PriceChartBody accountId={accountId} instrumentId={instrumentId} average={average} firstBuy={firstBuy}
        initialRange={prefs.price_range} />
    </section>
  );
}

/** The range buttons and the chart, without a heading: the price chart section and the Pulpit's tile (plan 9). */
export function PriceChartBody({ accountId, instrumentId, average, firstBuy, initialRange }: {
  accountId: number; instrumentId: number; average: Money | null; firstBuy: IsoDate | null; initialRange: PriceRange;
}) {
  const [range, setRange] = useState<PriceRange>(initialRange);
  // One request per range: the API keeps every day of a short range and thins only a long one to ≤ 800 points.
  const from = rangeFrom(range, firstBuy, todayIso());
  const prices = useQuery({
    queryKey: keys.positionPrices(accountId, instrumentId, from),
    queryFn: () => api.positionPrices(accountId, instrumentId, from),
    placeholderData: keepPreviousData,
  });
  return (
    <>
      <Segmented label="Zakres wykresu ceny" options={PRICE_RANGES} value={range} onChange={setRange} />
      {prices.isPending ? <Skeleton rows={3} />
        : prices.isError ? <ErrorState error={prices.error} onRetry={() => void prices.refetch()} />
          : <Chart data={prices.data} average={average} sinceBuy={range === "buy"} />}
    </>
  );
}
