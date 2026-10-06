import { useId, useMemo, useRef, useState } from "react";
import type { IsoDate, Money, PriceChartData } from "../api/types";
import { NBSP, formatDate } from "../format";
import { chartMarks, formatPrice, markerLabel, type ChartMark } from "../screens/positions/priceModel";
import { FRAME, frameFor, niceStep, type Frame } from "./geometry";
import styles from "./PriceChart.module.css";
import { timeTicks } from "./timeTicks";
import { useChartGestures } from "./useChartGestures";
import { useWidth } from "./useWidth";
import { clampWindow, drawnRange, fullWindow, type ChartWindow, type YRange } from "./viewport";

export const MARKER_COLORS = { buy: "var(--mark-buy)", sell: "var(--mark-sell)", dividend: "var(--mark-dividend)", average: "var(--mark-average)", note: "var(--mark-note)" } as const;

const PAD = 0.05;
const SAME_DAY_SHIFT = 16; // most of a 28 px tap target stays free beside its neighbour
const MARK_GAP = 9;
const DAY_MS = 86_400_000;
const f = (n: number) => n.toFixed(1);
const days = (iso: IsoDate) => Date.parse(`${iso}T00:00:00Z`) / DAY_MS;

/** Where `date` falls on the point indices: between the closes around it, on the last close after the last one,
 * nothing before the first. */
export function dateIndex(dates: IsoDate[], date: IsoDate): number | null {
  const after = dates.findIndex((d) => d >= date);
  if (after === -1) return dates.length - 1;
  if (dates[after] === date) return after;
  if (after === 0) return null;
  const before = dates[after - 1]!;
  return after - 1 + (days(date) - days(before)) / (days(dates[after]!) - days(before));
}

function closeAt(closes: number[], index: number): number {
  const lo = Math.floor(index);
  const hi = Math.min(lo + 1, closes.length - 1);
  return closes[lo]! + (closes[hi]! - closes[lo]!) * (index - lo);
}

/** Round ticks strictly inside the range. */
function priceTicks(min: number, max: number): number[] {
  const step = niceStep(max - min, 3);
  const ticks: number[] = [];
  for (let k = Math.floor(min / step) + 1; k * step < max; k++) ticks.push(Number((k * step).toFixed(8)));
  return ticks;
}

function tickLabel(value: number, step: number): string {
  const places = step >= 1 ? 0 : Math.min(Math.ceil(-Math.log10(step) - 1e-9), 4);
  const [whole, fraction] = value.toFixed(places).split(".");
  return `${whole!.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP)}${fraction ? `,${fraction}` : ""}`;
}

interface Placed { marker: ChartMark; index: number; at: number; shift: number }

/** Shifts operations of one day apart so each keeps its own tappable spot. */
function place(markers: ChartMark[], dates: IsoDate[], view: ChartWindow): Placed[] {
  const placed = markers.flatMap((marker, index) => {
    const at = dateIndex(dates, marker.date);
    return at === null || at < view.from - 1e-9 || at > view.to + 1e-9 ? [] : [{ marker, index, at, shift: 0 }];
  });
  const byDay = new Map<IsoDate, Placed[]>();
  for (const p of placed) byDay.set(p.marker.date, [...(byDay.get(p.marker.date) ?? []), p]);
  for (const group of byDay.values()) {
    group.forEach((p, k) => { p.shift = (k - (group.length - 1) / 2) * SAME_DAY_SHIFT; });
  }
  return placed;
}

function Mark({ kind, x, y, big }: { kind: ChartMark["kind"]; x: number; y: number; big: boolean }) {
  const r = big ? 7 : 5.5;
  if (kind === "note") {
    return (
      <g data-mark="note">
        <circle cx={x} cy={y} r={r + 1.5} fill={MARKER_COLORS.note} />
        <text x={x} y={y + 3.5} className={styles.dividend}>N</text>
      </g>
    );
  }
  if (kind === "dividend") {
    return (
      <g data-mark="dividend">
        <circle cx={x} cy={y} r={r + 1} fill={MARKER_COLORS.dividend} />
        <text x={x} y={y + 3.5} className={styles.dividend}>D</text>
      </g>
    );
  }
  const tip = kind === "buy" ? y - r : y + r; // ▲ points up at the price from below, ▼ down from above
  const base = kind === "buy" ? y + r : y - r;
  return <path data-mark={kind} d={`M${f(x)},${f(tip)}L${f(x + r)},${f(base)}L${f(x - r)},${f(base)}Z`} fill={MARKER_COLORS[kind]} />;
}

/** The instrument's closes in its own currency with the position's operations on them (spec 7e). */
export function PriceChart({ data, average, selected, onSelect, view: requested, onViewChange, onReset, maxHeight }: {
  data: PriceChartData;
  /** A tile of the Pulpit (plan 9b) caps the drawing to fit its height. */
  maxHeight?: number;
  /** The average purchase price (quote currency); null draws no line. */
  average: Money | null;
  selected: number | null;
  onSelect(index: number): void;
  view?: ChartWindow;
  onViewChange?: (view: ChartWindow) => void;
  onReset?: () => void;
}) {
  const dates = useMemo(() => data.points.map((p) => p.date), [data.points]);
  const closes = useMemo(() => data.points.map((p) => Number(p.close)), [data.points]);
  const marks = useMemo(() => chartMarks(data), [data]);
  const [figure, setFigure] = useState<HTMLElement | null>(null);
  const width = useWidth(figure, FRAME.width);
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const frame: Frame = frameFor(width, maxHeight);
  const count = dates.length;
  const view = clampWindow(requested ?? fullWindow(count), count);
  const shownY = useRef<YRange>({ min: 0, max: 1 });
  const gestures = useChartGestures({
    view, count, frame, y: () => shownY.current, manualY: false, scaleY: false, onYChange: () => {},
    onChange: (next) => {
      if (Math.abs(next.from - view.from) < 1e-6 && Math.abs(next.to - view.to) < 1e-6) return;
      onViewChange?.(next);
    },
    onReset: () => onReset?.(),
  });

  if (count < 2) return <p className={styles.note}>Brak notowań dla tego instrumentu.</p>;

  const placed = place(marks, dates, view);
  const firstShown = Math.ceil(view.from - 1e-9);
  const lastShown = Math.floor(view.to + 1e-9);
  const values = [
    ...closes.slice(firstShown, lastShown + 1),
    ...placed.flatMap((p) => (p.marker.price === null ? [] : [Number(p.marker.price)])),
  ];
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  const pad = hi > lo ? (hi - lo) * PAD : Math.max(Math.abs(lo) * 0.01, 0.01);
  lo -= pad;
  hi += pad;
  shownY.current = { min: lo, max: hi };
  const ticks = priceTicks(lo, hi);
  const step = ticks.length > 1 ? ticks[1]! - ticks[0]! : niceStep(hi - lo, 3);

  const plotRight = frame.width - frame.right;
  const baseline = frame.height - frame.bottom;
  const span = view.to - view.from || 1;
  const x = (index: number) => frame.left + ((index - view.from) / span) * (plotRight - frame.left);
  const y = (value: number) => frame.top + (1 - (value - lo) / (hi - lo)) * (baseline - frame.top);
  const { start, end } = drawnRange(view, count);
  const line = closes.slice(start, end + 1).map((c, k) => `${k ? "L" : "M"}${f(x(start + k))},${f(y(c))}`).join("");
  const timeLabels = timeTicks(dates.map((date) => ({ date, value: 0, invested: 0, flow: 0 })), view, plotRight - frame.left);
  const averageY = average === null ? null : y(Number(average));
  const showAverage = averageY !== null && averageY >= frame.top && averageY <= baseline;

  const spot = (p: Placed) => {
    const px = x(p.at) + p.shift;
    if (p.marker.kind === "note") return { x: px, y: Math.max(frame.top + 8, y(closeAt(closes, p.at)) - 2 * MARK_GAP) };
    if (p.marker.kind === "dividend") return { x: px, y: baseline - MARK_GAP };
    const price = p.marker.price === null ? closeAt(closes, p.at) : Number(p.marker.price);
    return { x: px, y: y(price) + (p.marker.kind === "buy" ? MARK_GAP : -MARK_GAP) };
  };

  return (
    <figure className={styles.chart} ref={setFigure}>
      {gestures.hint && <p className={styles.hint} role="status">Ctrl + kółko przybliża</p>}
      <div className={styles.stage}>
        <svg
          className={styles.svg}
          viewBox={`0 0 ${frame.width} ${frame.height}`}
          role="img"
          aria-label={`Wykres ceny od ${formatDate(dates[firstShown]!)} do ${formatDate(dates[lastShown]!)}`}
          ref={gestures.ref}
          onPointerDown={gestures.onPointerDown}
          onPointerMove={gestures.onPointerMove}
          onPointerUp={gestures.onPointerUp}
          onPointerCancel={gestures.onPointerUp}
          onDoubleClick={gestures.onDoubleClick}
        >
          <defs>
            <clipPath id={`plot-${id}`}><rect x={frame.left} y={0} width={plotRight - frame.left} height={frame.height} /></clipPath>
          </defs>
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={frame.left} x2={plotRight} y1={y(tick)} y2={y(tick)} className={styles.grid} />
              <text x={plotRight + 6} y={y(tick) + 4} className={styles.axis}>{tickLabel(tick, step)}</text>
            </g>
          ))}
          {timeLabels.map((tick) => (
            <g key={tick.index}>
              <line x1={x(tick.index)} x2={x(tick.index)} y1={frame.top} y2={baseline} className={styles.grid} />
              <text x={x(tick.index) + 3} y={frame.height - 4} className={tick.strong ? styles.axisStrong : styles.axis}>{tick.label}</text>
            </g>
          ))}
          <g clipPath={`url(#plot-${id})`}>
            {averageY !== null && !showAverage && (
              // Off the prices shown: no line, but the average stays in sight at the edge it lies beyond.
              <text x={frame.left + 4} y={averageY < frame.top ? frame.top + 11 : baseline - 4} className={styles.averageLabel}
                data-line="average">
                {`średnia ${formatPrice(average!, data.currency)} ${averageY < frame.top ? "↑" : "↓"}`}
              </text>
            )}
            {showAverage && (
              <g data-line="average">
                <line x1={frame.left} x2={plotRight} y1={averageY} y2={averageY} stroke={MARKER_COLORS.average} className={styles.average} />
                <text x={frame.left + 4} y={averageY - 4} className={styles.averageLabel}>
                  {`średnia ${formatPrice(average!, data.currency)}`}
                </text>
              </g>
            )}
            <path d={line} className={styles.price} data-line="price" />
            {placed.map((p) => {
              const at = spot(p);
              return <Mark key={p.index} kind={p.marker.kind} x={at.x} y={at.y} big={p.index === selected} />;
            })}
          </g>
        </svg>
        {placed.map((p) => {
          const at = spot(p);
          return (
            <button
              key={p.index}
              type="button"
              className={styles.hit}
              style={{ left: `${(at.x / frame.width) * 100}%`, top: `${(at.y / frame.height) * 100}%` }}
              aria-pressed={p.index === selected}
              aria-label={markerLabel(p.marker, data.currency)}
              onClick={() => onSelect(p.index)}
            />
          );
        })}
      </div>
    </figure>
  );
}
