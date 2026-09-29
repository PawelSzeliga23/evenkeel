import { useId, useMemo, useState, type PointerEvent } from "react";
import type { HistoryPoint } from "../api/types";
import { formatDate, formatMoney } from "../format";
import {
  FRAME, axisLabel, clipAbove, clipBelow, depositMarks, gapPath, linePath, monthTicks, nearestIndex, scales, stairPath,
  toChartPoints,
} from "./geometry";
import styles from "./ValueChart.module.css";

export function ValueChart({ points }: { points: HistoryPoint[] }) {
  const data = useMemo(() => toChartPoints(points), [points]);
  const [active, setActive] = useState<number | null>(null);
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");

  if (data.length < 2) {
    return <p className={styles.note}>Wykres pojawi się, gdy wycena obejmie co najmniej dwa dni.</p>;
  }

  const s = scales(data, FRAME);
  const last = data.length - 1;
  const baseline = FRAME.height - FRAME.bottom;
  const plotRight = FRAME.width - FRAME.right;
  const shown = active === null ? null : points[active]!;
  const gap = gapPath(data, s);

  function track(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    setActive(nearestIndex(((event.clientX - rect.left) / rect.width) * FRAME.width, data.length, FRAME));
  }

  return (
    <figure className={styles.chart}>
      <div className={styles.readout} aria-live="polite">
        {shown ? (
          <>
            <span className={styles.day}>{formatDate(shown.date)}</span>
            <span className="num">Wartość {formatMoney(shown.value_pln)}</span>
            <span className="num">Wpłacono {formatMoney(shown.invested_pln)}</span>
          </>
        ) : (
          <>
            <span className={styles.key}><i className={styles.swValue} />Wartość</span>
            <span className={styles.key}><i className={styles.swCapital} />Wpłacony kapitał</span>
            <span className={styles.key}><i className={styles.swDeposit} />Wpłata</span>
          </>
        )}
      </div>
      <svg
        className={styles.svg}
        viewBox={`0 0 ${FRAME.width} ${FRAME.height}`}
        role="img"
        aria-label={`Wykres wartości portfela od ${formatDate(points[0]!.date)} do ${formatDate(points[last]!.date)}`}
        onPointerMove={track}
        onPointerDown={track}
        onPointerLeave={() => setActive(null)}
      >
        <defs>
          <clipPath id={`above-${id}`}><path d={clipAbove(data, s, FRAME)} /></clipPath>
          <clipPath id={`below-${id}`}><path d={clipBelow(data, s, FRAME)} /></clipPath>
        </defs>
        {s.ticks.map((tick) => (
          <g key={tick}>
            <line x1={FRAME.left} x2={plotRight} y1={s.y(tick)} y2={s.y(tick)} className={styles.grid} />
            <text x={plotRight + 6} y={s.y(tick) + 4} className={styles.axis}>{axisLabel(tick)}</text>
          </g>
        ))}
        {monthTicks(data).map((tick) => (
          <text key={tick.index} x={s.x(tick.index)} y={FRAME.height - 4} className={styles.axis}>{tick.label}</text>
        ))}
        {depositMarks(data).map((mark) => (
          <line key={mark.index} x1={s.x(mark.index)} x2={s.x(mark.index)} y1={baseline + 2}
            y2={baseline + (mark.large ? 12 : 7)} className={styles.deposit} />
        ))}
        <path d={gap} fill="var(--amber-soft)" clipPath={`url(#above-${id})`} />
        <path d={gap} fill="var(--loss-soft)" clipPath={`url(#below-${id})`} />
        <path d={stairPath(data, s)} className={styles.capital} />
        <path d={linePath(data, s)} className={styles.value} pathLength={1} />
        {active !== null && <line x1={s.x(active)} x2={s.x(active)} y1={FRAME.top} y2={baseline} className={styles.cursor} />}
        <circle cx={s.x(last)} cy={s.y(data[last]!.value)} r={4} fill="var(--amber)" />
        <circle cx={s.x(last)} cy={s.y(data[last]!.value)} r={8} fill="var(--amber)" opacity={0.18} />
      </svg>
    </figure>
  );
}
