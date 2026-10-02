import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Money, PriceChartData, PriceMarker } from "../../api/types";
import { MARKER_COLORS, PriceChart } from "../../charts/PriceChart";
import { clampWindow, windowForRange, type ChartWindow } from "../../charts/viewport";
import { formatDate, formatDecimal, formatMoney, formatPercent, signOf, todayIso } from "../../format";
import { ErrorState, Skeleton } from "../../ui/States";
import { Segmented } from "../../ui/Segmented";
import ui from "../../ui/ui.module.css";
import { PRICE_RANGES, formatPrice, rangeFrom, type PriceRange } from "./priceModel";
import styles from "./Positions.module.css";

const TITLE_ID = "section-Wykres-ceny";
const KIND_NAMES: Record<PriceMarker["kind"], string> = { buy: "Zakup", sell: "Sprzedaż", dividend: "Dywidenda" };

/** The change from `base` to `last` in percent, as the API would write it ("29.01"); null without a base. */
function change(last: number, base: number | null): string | null {
  return base ? (((last - base) / base) * 100).toFixed(2) : null;
}

const tone = (value: string | null) => (value === null ? "" : signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

function Operation({ marker, last, currency }: { marker: PriceMarker; last: number; currency: string | null }) {
  const head = `${KIND_NAMES[marker.kind]}, ${formatDate(marker.date)}`;
  if (marker.kind === "dividend") {
    return (
      <div className={styles.operation} role="status">
        <b>{head}</b>
        <span className="num up">{formatMoney(marker.amount_pln, { sign: true })}</span>
      </div>
    );
  }
  const amount = formatMoney(marker.amount_pln.replace(/^-/, ""));
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

function Legend({ average }: { average: boolean }) {
  const items: [string, string][] = [["▲", "Zakup"], ["▼", "Sprzedaż"], ["D", "Dywidenda"]];
  const colors = [MARKER_COLORS.buy, MARKER_COLORS.sell, MARKER_COLORS.dividend];
  return (
    <p className={styles.legend}>
      {items.map(([mark, name], i) => (
        <span key={name}><b style={{ color: colors[i] }} aria-hidden="true">{mark}</b> {name}</span>
      ))}
      {average && <span><i className={styles.averageSwatch} style={{ borderColor: MARKER_COLORS.average }} /> Średnia cena zakupu</span>}
    </p>
  );
}

function Chart({ data, average }: { data: PriceChartData; average: Money | null }) {
  const [range, setRange] = useState<PriceRange>("buy");
  const [zoom, setZoom] = useState<ChartWindow | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const dates = data.points.map((p) => p.date);
  const from = rangeFrom(range, data.first_buy, todayIso());
  const rangeView = windowForRange(dates, from);
  const view = clampWindow(zoom ?? rangeView, dates.length);
  useEffect(() => setSelected(null), [data]);

  if (dates.length < 2) return <p className="dim">Brak notowań dla tego instrumentu.</p>;

  const last = Number(data.points[data.points.length - 1]!.close);
  const firstBuy = data.markers.find((m) => m.kind === "buy" && m.price !== null);
  const sinceBuy = range === "buy" && firstBuy !== undefined;
  const base = sinceBuy ? Number(firstBuy.price) : Number(data.points[Math.ceil(view.from - 1e-9)]!.close);
  const moved = change(last, base);
  const marker = selected === null ? null : data.markers[selected] ?? null;

  return (
    <>
      <p className={styles.priceHead}>
        <b className="num">{formatPrice(data.points[data.points.length - 1]!.close, data.currency)}</b>
        {moved !== null && <span className={`num ${tone(moved)}`}>{`${formatPercent(moved)} ${sinceBuy ? "od 1. zakupu" : "w zakresie"}`}</span>}
      </p>
      <Segmented label="Zakres wykresu ceny" options={PRICE_RANGES} value={range}
        onChange={(next) => { setRange(next); setZoom(null); }} />
      <PriceChart data={data} average={average} selected={selected} onSelect={setSelected}
        view={view} onViewChange={setZoom} onReset={() => setZoom(null)} />
      <Legend average={average !== null} />
      {marker && <Operation marker={marker} last={last} currency={data.currency} />}
      <p className={styles.hint}>Szczypnij lub przesuń, żeby zmienić zakres; dotknij znacznika, żeby zobaczyć operację.</p>
    </>
  );
}

/** Wykres ceny (spec 7e): the instrument's price in its currency with the position's operations on it. */
export function PriceSection({ accountId, instrumentId, average }: {
  accountId: number; instrumentId: number; average: Money | null;
}) {
  // One request without `from`: the API thins the whole history to ≤ 800 points, every range is a window on it.
  const prices = useQuery({
    queryKey: keys.positionPrices(accountId, instrumentId, null),
    queryFn: () => api.positionPrices(accountId, instrumentId, null),
  });
  return (
    <section className={ui.section} aria-labelledby={TITLE_ID}>
      <h2 id={TITLE_ID} className={ui.sectionTitle}>Wykres ceny</h2>
      {prices.isPending ? <Skeleton rows={3} />
        : prices.isError ? <ErrorState error={prices.error} onRetry={() => void prices.refetch()} />
          : <Chart data={prices.data} average={average} />}
    </section>
  );
}
