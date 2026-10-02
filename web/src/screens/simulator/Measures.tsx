import type { ReactNode } from "react";
import type { ScenarioMeasures } from "../../api/types";
import { swatchStyle } from "../../charts/ComparisonChart";
import { formatPercent, signOf } from "../../format";
import { Money } from "../../ui/Amount";
import { HELP } from "../../ui/help";
import { InfoTip } from "../../ui/InfoTip";
import ui from "../../ui/ui.module.css";
import { shownReturn } from "../analysis/model";
import styles from "./Simulator.module.css";

export interface Column { key: string; label: string; color: string; dashed?: boolean; measures: ScenarioMeasures | null }

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");
const percent = (value: string | null, sign = true) =>
  <span className={`num ${sign ? tone(value) : ""}`}>{formatPercent(value, { places: 1, sign })}</span>;

const ROWS: { label: string; value: (m: ScenarioMeasures) => ReactNode }[] = [
  { label: "Wartość", value: (m) => <Money value={m.value_pln} /> },
  { label: "Wpłacono", value: (m) => <Money value={m.invested_pln} /> },
  { label: "Zysk", value: (m) => <Money value={m.profit_pln} sign tone /> },
  { label: "XIRR", value: (m) => percent(shownReturn(m.xirr, m.period.annualized).value) },
  { label: "TWR", value: (m) => percent(shownReturn(m.twr, m.period.annualized).value) },
  { label: "Maks. obsunięcie", value: (m) => percent(m.max_drawdown?.pct ?? null) },
  { label: "Zmienność", value: (m) => percent(m.volatility_pct, false) },
];

/** A card per line; the "?" explanations sit in the first card only. */
export function Measures({ columns }: { columns: Column[] }) {
  return (
    <div className={styles.columns}>
      {columns.map((column, index) => (
        <section key={column.key} className={styles.column} role="group" aria-label={column.label}>
          <div className={styles.columnHead}>
            <i className={styles.swatch} style={swatchStyle(column.color, column.dashed)} />
            <span>{column.label}</span>
          </div>
          {column.measures ? (
            <dl className={ui.kv}>
              {ROWS.map((row) => [
                <dt key={`${row.label}-t`} className={styles.label}>
                  {row.label}{index === 0 && <InfoTip label={row.label} help={HELP[row.label]!} />}
                </dt>,
                <dd key={`${row.label}-d`}>{row.value(column.measures!)}</dd>,
              ])}
            </dl>
          ) : <p className={styles.hint}>Brak wyceny w tym okresie.</p>}
        </section>
      ))}
    </div>
  );
}
