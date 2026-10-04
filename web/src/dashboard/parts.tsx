/** Plan 9: what every tile is made of — its section with a title, its problems, a figure of a metric. */
import { useQuery } from "@tanstack/react-query";
import { useId, type ReactNode } from "react";
import { Link } from "react-router";
import { useAccountSelection } from "../accounts/AccountSelection";
import { api } from "../api/endpoints";
import { keys } from "../api/queryKeys";
import type { Analytics, AnalyticsPeriod, Summary } from "../api/types";
import { formatDecimal, formatPercent, signOf } from "../format";
import { Money } from "../ui/Amount";
import { InfoTip } from "../ui/InfoTip";
import { RECALC_POLL_MS } from "../screens/dashboard/model";
import ui from "../ui/ui.module.css";
import styles from "./Dashboard.module.css";
import { METRICS, metricValue, type MetricKey } from "./metrics";

export function TileSection({ title, more, children }: {
  title: string; more?: { to: string; label: string; text?: string }; children: ReactNode;
}) {
  const id = useId();
  return (
    <section className={styles.tileSection} aria-labelledby={id}>
      <div className={ui.sectionHead}>
        <h2 id={id} className={ui.sectionTitle}>{title}</h2>
        {more && <Link className={ui.sectionMore} to={more.to} aria-label={more.label}>{more.text ?? "Szczegóły"}</Link>}
      </div>
      {children}
    </section>
  );
}

/** A tile that could not load: the rest of the Pulpit keeps working. */
export function TileError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className={styles.tileProblem}>
      <p>Nie udało się wczytać.</p>
      <button type="button" className={styles.tileRetry} onClick={onRetry}>Ponów</button>
    </div>
  );
}

export function TileNote({ children }: { children: ReactNode }) {
  return <p className={styles.tileProblem}>{children}</p>;
}

const tone = (value: string | null) => (value === null ? "" : signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

/** One metric: its name with „?”, its value and caption. */
export function MetricFigure({ metric, summary, analytics }: {
  metric: MetricKey; summary: Summary; analytics: Analytics | undefined;
}) {
  const info = METRICS[metric];
  const { value, format, tone: toned, note } = metricValue(metric, summary, analytics);
  let shown: ReactNode;
  if (value === null) shown = <span className="num dim">—</span>;
  else if (format === "money") shown = <Money value={value} sign={toned} tone={toned} />;
  else {
    const text = format === "percent" ? formatPercent(value, { places: 1, sign: toned }) : formatDecimal(value, 2);
    shown = <span className={`num ${toned ? tone(value) : ""}`}>{text}</span>;
  }
  return (
    <div className={styles.tileFigure}>
      <dt><span>{info.label}</span>{info.help && <InfoTip label={info.label} help={info.help} />}</dt>
      <dd>{shown}</dd>
      {note && <small>{note}</small>}
    </div>
  );
}

/** The analytics of the chosen accounts for a period; asked only when a tile needs them. */
export function useTileAnalytics(period: AnalyticsPeriod, needed: boolean) {
  const [accountIds, , ready] = useAccountSelection();
  return useQuery({
    queryKey: keys.analytics(accountIds, period), queryFn: () => api.analytics(accountIds, period),
    enabled: ready && needed,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
  });
}

export const needsAnalytics = (metrics: readonly MetricKey[]) => metrics.some((m) => METRICS[m].source === "analytics");

/** A small tile (plan 9b): the one thing that matters, its name leading to the details. */
export function TileBrief({ title, to, value, note, children }: {
  title: string; to?: string; value: ReactNode; note?: ReactNode; children?: ReactNode;
}) {
  const id = useId();
  return (
    <section className={styles.tileBrief} aria-labelledby={id}>
      <h2 id={id} className={styles.tileBriefTitle}>{to ? <Link to={to}>{title}</Link> : title}</h2>
      <div className={styles.tileBriefValue}>{value}</div>
      {note && <small className={styles.tileBriefNote}>{note}</small>}
      {children}
    </section>
  );
}

/** A line of values without axes, for small tiles (plan 9b). */
export function Sparkline({ values, label }: { values: number[]; label: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const path = values.map((v, i) => `${i ? "L" : "M"}${((i / (values.length - 1)) * 100).toFixed(2)} ${(30 - ((v - min) / span) * 28).toFixed(2)}`).join(" ");
  return (
    <svg className={styles.sparkline} viewBox="0 0 100 32" preserveAspectRatio="none" role="img" aria-label={label}>
      <path d={path} />
    </svg>
  );
}
