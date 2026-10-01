import { useId, useMemo, useRef, useState, type PointerEvent } from "react";
import type { HistoryPoint } from "../api/types";
import { formatDate, formatMoney } from "../format";
import {
  FRAME, axisLabel, clipAbove, clipBelow, depositMarks, frameFor, gapPath, indexAt, linePath, scales, stairPath,
  toChartPoints,
} from "./geometry";
import { timeTicks } from "./timeTicks";
import { useChartGestures } from "./useChartGestures";
import { useWidth } from "./useWidth";
import { clampWindow, drawnRange, fullWindow, type ChartWindow, type YRange } from "./viewport";
import styles from "./ValueChart.module.css";

export function ValueChart({ points, view: requested, yRange = null, onViewChange, onYRangeChange, onReset }: {
  points: HistoryPoint[];
  view?: ChartWindow;
  /** Amounts set by hand by dragging the Y axis; null follows the visible data. */
  yRange?: YRange | null;
  onViewChange?: (view: ChartWindow) => void;
  onYRangeChange?: (range: YRange) => void;
  onReset?: () => void;
}) {
  const data = useMemo(() => toChartPoints(points), [points]);
  const marks = useMemo(() => depositMarks(data), [data]);
  const [active, setActive] = useState<number | null>(null);
  const [figure, setFigure] = useState<HTMLElement | null>(null);
  const width = useWidth(figure, FRAME.width);
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const frame = frameFor(width);
  const view = clampWindow(requested ?? fullWindow(data.length), data.length);
  const shownY = useRef<YRange>({ min: 0, max: 1 });
  const gestures = useChartGestures({
    view, count: data.length, frame,
    y: () => shownY.current,
    manualY: yRange !== null,
    onYChange: (range) => { setActive(null); onYRangeChange?.(range); },
    onChange: (next) => {
      // A gesture held back by the history's edges changes nothing and must not count as a zoom.
      if (Math.abs(next.from - view.from) < 1e-6 && Math.abs(next.to - view.to) < 1e-6) return;
      setActive(null);
      onViewChange?.(next);
    },
    onReset: () => onReset?.(),
  });

  if (data.length < 2) {
    return <p className={styles.note}>Wykres pojawi się, gdy wycena obejmie co najmniej dwa dni.</p>;
  }

  const { start, end } = drawnRange(view, data.length);
  const drawn = data.slice(start, end + 1);
  const s = scales(drawn, frame, { from: view.from - start, to: view.to - start }, yRange);
  shownY.current = { min: s.min, max: s.max };
  const x = (index: number) => s.x(index - start);
  const last = data.length - 1;
  const firstShown = Math.ceil(view.from - 1e-9);
  const lastShown = Math.floor(view.to + 1e-9);
  const baseline = frame.height - frame.bottom;
  const plotRight = frame.width - frame.right;
  const shown = active === null ? null : points[active]!;
  const gap = gapPath(drawn, s);
  const ticks = timeTicks(data, view, plotRight - frame.left);

  function track(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    setActive(indexAt(((event.clientX - rect.left) / rect.width) * frame.width, view, frame, data.length));
  }

  return (
    <figure className={styles.chart} ref={setFigure}>
      {gestures.hint && <p className={styles.hint} role="status">Ctrl + kółko przybliża</p>}
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
        viewBox={`0 0 ${frame.width} ${frame.height}`}
        role="img"
        aria-label={`Wykres wartości portfela od ${formatDate(points[firstShown]!.date)} do ${formatDate(points[lastShown]!.date)}`}
        ref={gestures.ref}
        onPointerDown={(event) => { if (!gestures.onPointerDown(event)) track(event); }}
        onPointerMove={(event) => { if (!gestures.onPointerMove(event)) track(event); }}
        onPointerUp={gestures.onPointerUp}
        onPointerCancel={gestures.onPointerUp}
        onPointerLeave={() => setActive(null)}
        onDoubleClick={gestures.onDoubleClick}
      >
        <defs>
          <clipPath id={`plot-${id}`}><rect x={frame.left} y={frame.top} width={plotRight - frame.left} height={baseline - frame.top} /></clipPath>
          <clipPath id={`strip-${id}`}><rect x={frame.left} y={0} width={plotRight - frame.left} height={frame.height} /></clipPath>
          <clipPath id={`above-${id}`}><path d={clipAbove(drawn, s, frame)} /></clipPath>
          <clipPath id={`below-${id}`}><path d={clipBelow(drawn, s, frame)} /></clipPath>
        </defs>
        {s.ticks.map((tick) => (
          <g key={tick}>
            <line x1={frame.left} x2={plotRight} y1={s.y(tick)} y2={s.y(tick)} className={styles.grid} />
            <text x={plotRight + 6} y={s.y(tick) + 4} className={styles.axis}>{axisLabel(tick, s.ticks.length > 1 ? s.ticks[1]! - s.ticks[0]! : Infinity)}</text>
          </g>
        ))}
        {ticks.map((tick) => (
          <g key={tick.index}>
            <line x1={x(tick.index)} x2={x(tick.index)} y1={frame.top} y2={baseline} className={styles.grid} />
            <text x={x(tick.index) + 3} y={frame.height - 4} className={tick.strong ? styles.axisStrong : styles.axis}>{tick.label}</text>
          </g>
        ))}
        <g clipPath={`url(#strip-${id})`}>
          {marks.filter((mark) => mark.index >= start && mark.index <= end).map((mark) => (
            <line key={mark.index} x1={x(mark.index)} x2={x(mark.index)} y1={baseline + 2}
              y2={baseline + (mark.large ? 12 : 7)} className={styles.deposit} />
          ))}
        </g>
        <rect x={plotRight} y={frame.top} width={frame.right} height={baseline - frame.top} className={styles.yAxis} />
        <g clipPath={`url(#plot-${id})`}>
          <path d={gap} fill="var(--amber-soft)" clipPath={`url(#above-${id})`} />
          <path d={gap} fill="var(--loss-soft)" clipPath={`url(#below-${id})`} />
          <path d={stairPath(drawn, s)} className={styles.capital} />
          <path d={linePath(drawn, s)} className={styles.value} pathLength={1} />
        </g>
        {active !== null && <line x1={x(active)} x2={x(active)} y1={frame.top} y2={baseline} className={styles.cursor} />}
        {lastShown === last && data[last]!.value >= s.min && data[last]!.value <= s.max && (
          <>
            <circle cx={x(last)} cy={s.y(data[last]!.value)} r={4} fill="var(--amber)" />
            <circle cx={x(last)} cy={s.y(data[last]!.value)} r={8} fill="var(--amber)" opacity={0.18} />
          </>
        )}
      </svg>
    </figure>
  );
}
