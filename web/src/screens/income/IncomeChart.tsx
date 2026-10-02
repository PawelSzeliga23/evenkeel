import { useState } from "react";
import { useWidth } from "../../charts/useWidth";
import { formatMoney } from "../../format";
import styles from "./Income.module.css";
import type { Bucket } from "./model";

const DEFAULT_W = 340;
const H = 180;
const TOP = 6;
const BOTTOM = 20;
const PLOT_H = H - TOP - BOTTOM;
const MIN_LABEL_W = 28;

export const PARTS = {
  income: [
    { key: "interest", label: "odsetki", color: "#5DB98A" },
    { key: "dividends", label: "dywidendy", color: "#7FB6E6" },
  ],
  costs: [
    { key: "fx", label: "przewalutowanie", color: "#E0676E" },
    { key: "taxes", label: "podatki", color: "#B07FE0" },
    { key: "fees", label: "opłaty", color: "#F0A43A" },
  ],
} as const;

const money = (value: number) => formatMoney(value.toFixed(2), { sign: true });

/** Income stacked over the zero line and costs under it, a column per month (or year); a column is a button. */
export function IncomeChart({ buckets, selected, onSelect }: {
  buckets: Bucket[]; selected: string | null; onSelect: (key: string) => void;
}) {
  const [box, setBox] = useState<HTMLElement | null>(null);
  const W = useWidth(box, DEFAULT_W);
  // Only positive parts are drawn, so only they size the plot.
  const drawn = (b: Bucket, parts: readonly { key: keyof Bucket }[]) => parts.reduce((sum, p) => sum + Math.max(0, b[p.key] as number), 0);
  const up = Math.max(0, ...buckets.map((b) => drawn(b, PARTS.income)));
  const down = Math.max(0, ...buckets.map((b) => drawn(b, PARTS.costs)));
  const span = up + down;
  const zero = TOP + (span > 0 ? (up / span) * PLOT_H : PLOT_H / 2);
  const scale = span > 0 ? PLOT_H / span : 0;
  const column = buckets.length ? W / buckets.length : W;
  const bar = Math.max(4, Math.min(28, column * 0.6));
  const every = Math.max(1, Math.ceil(MIN_LABEL_W / column));

  return (
    <div ref={setBox} className={styles.chart}>
      <svg role="img" aria-label="Dochód i koszty w miesiącach" viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
        {buckets.map((b, i) => {
          const x = i * column + (column - bar) / 2;
          let top = zero;
          let bottom = zero;
          return (
            <g key={b.key} opacity={selected && selected !== b.key ? 0.45 : 1}>
              {PARTS.income.map((part) => {
                const h = b[part.key] * scale;
                if (h <= 0) return null;
                top -= h;
                return <rect key={part.key} data-part={part.key} x={x} y={top} width={bar} height={h} fill={part.color} />;
              })}
              {PARTS.costs.map((part) => {
                const h = b[part.key] * scale;
                if (h <= 0) return null;
                const y = bottom;
                bottom += h;
                return <rect key={part.key} data-part={part.key} x={x} y={y} width={bar} height={h} fill={part.color} />;
              })}
              {i % every === 0 && (
                <text x={i * column + column / 2} y={H - 6} textAnchor="middle" className={styles.tick}>{b.label}</text>
              )}
            </g>
          );
        })}
        <line data-zero x1={0} x2={W} y1={zero} y2={zero} className={styles.zero} />
      </svg>
      {buckets.map((b, i) => (
        <button key={b.key} type="button" className={styles.hit} aria-pressed={selected === b.key}
          aria-label={`${b.title}: dochód ${money(b.income)}, koszty ${money(-b.costs)}`}
          style={{ left: i * column, width: column }} onClick={() => onSelect(b.key)} />
      ))}
    </div>
  );
}
