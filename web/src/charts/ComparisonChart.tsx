import { useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";
import type { IsoDate, Money } from "../api/types";
import { formatDate, formatMoney } from "../format";
import styles from "./ComparisonChart.module.css";
import { axisLabel, niceStep, yDomain } from "./geometry";
import { timeTicks } from "./timeTicks";
import { useWidth } from "./useWidth";
import { fullWindow } from "./viewport";

/** One line: a value per date of the chart (null where it has none, e.g. before its first day). */
export interface ComparisonLine { key: string; label: string; color: string; dashed?: boolean; values: (Money | null)[] }

const DEFAULT_W = 350;
const H = 220;
const RIGHT = 48;
const TOP = 8;
const BOTTOM = 22;
const DASH = "6 4";

export function swatchStyle(color: string, dashed = false): CSSProperties {
  return { background: dashed ? `repeating-linear-gradient(90deg, ${color} 0 5px, transparent 5px 8px)` : color };
}

const toNumber = (value: Money | null) => (value === null ? null : Number(value));

function linePath(values: (number | null)[], x: (i: number) => number, y: (v: number) => number): string {
  let d = "";
  let pen = false;
  values.forEach((value, i) => {
    if (value === null) { pen = false; return; }
    d += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${y(value).toFixed(1)}`;
    pen = true;
  });
  return d;
}

/** Several value lines over the same days, without zoom (spec 7b §5); hover or ←/→ reads one day out. Without
 * `invested` there is no invested line; `unit="percent"` writes the axis in percent and `format` the readout. */
export function ComparisonChart({ dates, lines, invested = [], format = formatMoney, unit = "money" }: {
  dates: IsoDate[]; lines: ComparisonLine[]; invested?: (Money | null)[];
  format?: (value: Money) => string; unit?: "money" | "percent";
}) {
  const [figure, setFigure] = useState<HTMLElement | null>(null);
  const width = useWidth(figure, DEFAULT_W);
  const [hover, setHover] = useState<number | null>(null);
  const numbers = [...lines.flatMap((line) => line.values), ...invested]
    .filter((value): value is Money => value !== null).map(Number);
  if (dates.length < 2 || numbers.length === 0) {
    return <p className={styles.note}>Wykres pojawi się, gdy okres obejmie co najmniej dwa dni.</p>;
  }

  const last = dates.length - 1;
  const plotW = width - RIGHT;
  const plotH = H - TOP - BOTTOM;
  const domain = yDomain(numbers.map((value) => ({ date: "", value, invested: value, flow: 0 })));
  const step = domain.ticks.length > 1 ? domain.ticks[1]! - domain.ticks[0]! : niceStep(domain.max - domain.min, 3);
  const x = (i: number) => (i / last) * plotW;
  const y = (v: number) => TOP + (1 - (v - domain.min) / (domain.max - domain.min)) * plotH;
  const ticks = timeTicks(dates.map((date) => ({ date, value: 0, invested: 0, flow: 0 })), fullWindow(dates.length), plotW);
  const at = Math.min(hover ?? last, last);

  const move = (event: PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    if (box.width <= 0) return;
    const px = ((event.clientX - box.left) / box.width) * width;
    setHover(Math.min(Math.max(Math.round((px / plotW) * last), 0), last));
  };
  const key = (event: KeyboardEvent<SVGSVGElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    setHover(Math.min(Math.max(at + (event.key === "ArrowLeft" ? -1 : 1), 0), last));
  };
  const money = (value: Money | null | undefined) => (value == null ? "—" : format(value));
  const label = (tick: number) => (unit === "percent" ? `${axisLabel(tick, step)} %` : axisLabel(tick, step));
  const withInvested = invested.length > 0;

  return (
    <figure ref={setFigure} className={styles.chart}>
      <div className={styles.readout}>
        <span className={`${styles.cell} ${styles.day}`} data-readout-cell>{formatDate(dates[at]!)}</span>
        {lines.map((line) => (
          <span key={line.key} className={styles.cell} data-readout-cell>
            <i className={styles.swatch} style={swatchStyle(line.color, line.dashed)} />
            <span className={styles.name}>{line.label}</span> <b>{money(line.values[at])}</b>
          </span>
        ))}
        {withInvested && (
          <span className={styles.cell} data-readout-cell>
            <i className={styles.swatch} style={swatchStyle("var(--dim)")} /><span className={styles.name}>Wpłacono (portfel)</span> <b>{money(invested[at])}</b>
          </span>
        )}
      </div>
      <svg className={styles.svg} viewBox={`0 0 ${width} ${H}`} role="img" tabIndex={0}
        aria-label={`${unit === "percent" ? "Udział w portfelu" : "Porównanie wartości"}: ${lines.map((line) => line.label).join(", ")}`}
        onPointerMove={move} onPointerLeave={() => setHover(null)} onKeyDown={key} onBlur={() => setHover(null)}>
        {domain.ticks.map((tick) => (
          <g key={tick}>
            <line className={styles.grid} x1={0} x2={plotW} y1={y(tick)} y2={y(tick)} />
            <text className={styles.axis} x={plotW + 6} y={y(tick) + 4}>{label(tick)}</text>
          </g>
        ))}
        {withInvested && <path className={styles.capital} d={linePath(invested.map(toNumber), x, y)} data-line="invested" />}
        {lines.map((line) => (
          <path key={line.key} className={styles.line} d={linePath(line.values.map(toNumber), x, y)} stroke={line.color}
            strokeDasharray={line.dashed ? DASH : undefined} data-line={line.key} />
        ))}
        {hover !== null && <line className={styles.cursor} x1={x(at)} x2={x(at)} y1={TOP} y2={TOP + plotH} />}
        {ticks.map((tick) => (
          <text key={tick.index} className={styles.axis} x={x(tick.index)} y={H - 4} textAnchor="middle">{tick.label}</text>
        ))}
      </svg>
    </figure>
  );
}
