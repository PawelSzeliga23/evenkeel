/** Plan 9: tiles of figures — the value of the portfolio, one metric, the analysis. */
import { useId } from "react";
import type { Summary } from "../../api/types";
import { formatMoney, formatPercent, pluralPl, signOf } from "../../format";
import { HeroAmount, Money } from "../../ui/Amount";
import { Skeleton } from "../../ui/States";
import { DrawdownChart } from "../../charts/DrawdownChart";
import base from "../../screens/dashboard/Dashboard.module.css";
import styles from "../Dashboard.module.css";
import type { Tile } from "../layout";
import { METRICS } from "../metrics";
import { MetricFigure, TileError, TileNote, TileSection, needsAnalytics, useTileAnalytics } from "../parts";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

/** Today's top of the Pulpit: the payout value, the market value and exit costs, today's change, four figures. */
export function SummaryTile({ tile, summary }: { tile: Tile<"summary">; summary: Summary }) {
  const titleId = useId();
  const fields = tile.settings.fields;
  const analytics = useTileAnalytics("all", needsAnalytics(fields));
  const approximate = summary.approximate_positions;
  return (
    <section className={base.hero} aria-labelledby={titleId}>
      <span id={titleId} className="dim">Wartość portfela</span>
      <HeroAmount value={summary.value_pln} size={tile.size === "M" ? "m" : "l"} />
      {signOf(summary.exit_cost_pln) > 0 && (
        <p className="dim num">
          {`Wartość rynkowa ${formatMoney(summary.market_value_pln)} · koszty wyjścia ${formatMoney(`-${summary.exit_cost_pln}`)}`}
        </p>
      )}
      {summary.day_change_pln !== null && (
        <p className={base.today}>
          <Money value={summary.day_change_pln} sign tone />{" "}
          <span className={`num ${tone(summary.day_change_pct)}`}>({formatPercent(summary.day_change_pct)})</span>{" "}
          <span className="dim">dziś</span>
        </p>
      )}
      <dl className={styles.tileMetrics}>
        {fields.map((metric) => <MetricFigure key={metric} metric={metric} summary={summary} analytics={analytics.data} />)}
      </dl>
      {approximate > 0 && (
        <p className="flag">
          {approximate} {pluralPl(approximate, "pozycja wyceniona", "pozycje wycenione", "pozycji wycenionych")} w przybliżeniu
        </p>
      )}
    </section>
  );
}

export function MetricTile({ tile, summary }: { tile: Tile<"metric">; summary: Summary }) {
  const titleId = useId();
  const { metric } = tile.settings;
  const analytics = useTileAnalytics("all", needsAnalytics([metric]));
  return (
    <section aria-labelledby={titleId}>
      <span id={titleId} hidden>{METRICS[metric].label}</span>
      {analytics.isError ? <TileError onRetry={() => void analytics.refetch()} />
        : <dl className={styles.tileSection}><MetricFigure metric={metric} summary={summary} analytics={analytics.data} /></dl>}
    </section>
  );
}

const PERIOD_NAMES = { "1m": "1 mies.", "3m": "3 mies.", "1y": "1 rok", ytd: "od pocz. roku", all: "cały okres" } as const;

export function AnalysisTile({ tile, summary }: { tile: Tile<"analysis">; summary: Summary }) {
  const { metrics, period } = tile.settings;
  const analytics = useTileAnalytics(period, true);
  const data = analytics.data;
  return (
    <TileSection title="Analiza" more={{ to: "/analiza", label: "Szczegóły analizy" }}>
      <span className="dim">{PERIOD_NAMES[period]}</span>
      {analytics.isPending ? <Skeleton rows={2} />
        : analytics.isError ? <TileError onRetry={() => void analytics.refetch()} />
          : data!.period === null ? <TileNote>Brak wyceny w tym okresie.</TileNote> : (
            <>
              <dl className={styles.tileMetrics}>
                {metrics.map((m) => <MetricFigure key={m} metric={m} summary={summary} analytics={data} />)}
              </dl>
              {tile.size === "L" && data!.drawdown_series.length > 1 && <DrawdownChart points={data!.drawdown_series} />}
            </>
          )}
    </TileSection>
  );
}
