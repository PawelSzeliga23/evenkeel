import { useState, type PointerEvent } from "react";
import { formatDate, formatPercent } from "../format";
import { bands, monthlyRows, thin, type SharePoint, type ShareSeries } from "./shares";
import styles from "./ShareChart.module.css";

const W = 350;
const H = 170;
const RIGHT = 36;
const PLOT = W - RIGHT;
const MAX_POINTS = 120;

const pct = (share: number) => formatPercent((share * 100).toFixed(2), { sign: false, places: 1 });

export function ShareChart({ series, points }: { series: ShareSeries[]; points: SharePoint[] }) {
  const [active, setActive] = useState<number | null>(null);
  const shown = thin(points, MAX_POINTS);
  if (shown.length < 2) return <p className={styles.note}>Wykres pojawi się, gdy wycena obejmie co najmniej dwa dni.</p>;

  const paths = bands(shown, PLOT, H);
  const last = shown.length - 1;
  const point = active === null ? null : shown[active]!;

  function track(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    const x = ((event.clientX - rect.left) / rect.width) * W;
    setActive(Math.min(Math.max(Math.round((x / PLOT) * last), 0), last));
  }

  return (
    <figure className={styles.chart}>
      <ul className={styles.legend} aria-label="Legenda">
        {series.map((s) => <li key={s.key}><i className={styles.swatch} style={{ background: s.color }} />{s.label}</li>)}
      </ul>
      <div className={styles.readout} aria-live="polite">
        {point && (
          <>
            <span>{formatDate(point.date)}</span>
            {series.map((s, k) => <span key={s.key} className="num">{`${s.label} ${pct(point.shares[k]!)}`}</span>)}
          </>
        )}
      </div>
      <svg className={styles.svg} viewBox={`0 0 ${W} ${H + 18}`} role="img"
        aria-label={`Udział walut w czasie, od ${formatDate(shown[0]!.date)} do ${formatDate(shown[last]!.date)}`}
        onPointerMove={track} onPointerDown={track} onPointerLeave={() => setActive(null)}>
        {paths.map((d, k) => (
          <path key={series[k]!.key} d={d} fill={series[k]!.color} stroke="var(--night)" strokeWidth={1} strokeLinejoin="round" />
        ))}
        {[0, 0.5, 1].map((share) => (
          <g key={share}>
            <line className={styles.grid} x1={0} x2={PLOT} y1={H * (1 - share)} y2={H * (1 - share)} opacity={0.35} />
            <text className={styles.axis} x={PLOT + 6} y={H * (1 - share) + 3}>{`${share * 100}%`}</text>
          </g>
        ))}
        <text className={styles.axis} x={0} y={H + 14}>{formatDate(shown[0]!.date)}</text>
        <text className={styles.axis} x={PLOT} y={H + 14} textAnchor="end">{formatDate(shown[last]!.date)}</text>
        {active !== null && <line className={styles.cursor} x1={(active / last) * PLOT} x2={(active / last) * PLOT} y1={0} y2={H} />}
      </svg>
      <details>
        <summary>Pokaż tabelę</summary>
        <table className={styles.table}>
          <thead>
            <tr><th scope="col">Dzień</th>{series.map((s) => <th key={s.key} scope="col">{s.label}</th>)}</tr>
          </thead>
          <tbody>
            {monthlyRows(points).map((row) => (
              <tr key={row.date}>
                <td>{formatDate(row.date)}</td>
                {row.shares.map((share, k) => <td key={series[k]!.key}>{pct(share)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
