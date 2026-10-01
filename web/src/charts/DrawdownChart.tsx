import { useState } from "react";
import { formatPercent } from "../format";
import type { ChartPoint } from "./geometry";
import styles from "./DrawdownChart.module.css";
import { timeTicks } from "./timeTicks";
import { useWidth } from "./useWidth";
import { fullWindow } from "./viewport";

const DEFAULT_W = 350;
const H = 150;
const LEFT = 44;
const TOP = 8;
const BOTTOM = 22;
const PLOT_H = H - TOP - BOTTOM;

/** The fall below the running record on each day of the period (0 at a record, negative below it). */
export function DrawdownChart({ points }: { points: { date: string; pct: string }[] }) {
  const [figure, setFigure] = useState<HTMLElement | null>(null);
  const W = useWidth(figure, DEFAULT_W);
  const PLOT_W = W - LEFT;
  if (points.length < 2) return <p className={styles.note}>Wykres pojawi się, gdy okres obejmie co najmniej dwa dni.</p>;
  const values = points.map((p) => Number(p.pct));
  const deepest = Math.min(...values);
  const floor = Math.min(deepest, -1);
  const x = (i: number) => LEFT + (i / (points.length - 1)) * PLOT_W;
  const y = (v: number) => TOP + (v / floor) * PLOT_H;
  const line = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(points.length - 1).toFixed(1)} ${TOP} L${LEFT} ${TOP} Z`;
  const chartPoints: ChartPoint[] = points.map((p, i) => ({ date: p.date, value: values[i]!, invested: 0, flow: 0 }));
  const ticks = timeTicks(chartPoints, fullWindow(points.length), PLOT_W);
  const lowest = formatPercent(floor.toFixed(2), { places: 1 });

  return (
    <figure ref={setFigure} className={styles.chart}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`Obsunięcie w czasie, najgłębiej ${formatPercent(deepest.toFixed(2), { places: 1 })}`}>
        <line className={styles.grid} x1={LEFT} x2={W} y1={TOP} y2={TOP} />
        <line className={styles.grid} x1={LEFT} x2={W} y1={TOP + PLOT_H} y2={TOP + PLOT_H} strokeDasharray="2 3" />
        <text className={styles.label} x={0} y={TOP + 4}>0 %</text>
        <text className={styles.label} x={0} y={TOP + PLOT_H + 4}>{lowest}</text>
        <path className={styles.area} d={area} />
        <path className={styles.line} d={line} />
        {ticks.map((tick) => (
          <text key={tick.index} className={styles.label} x={x(tick.index)} y={H - 4} textAnchor="middle">{tick.label}</text>
        ))}
      </svg>
    </figure>
  );
}
