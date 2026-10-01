import type { MonthReturns } from "../../api/types";
import { formatPercent, signOf } from "../../format";
import styles from "./Analysis.module.css";
import { MONTHS, cellBackground } from "./model";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

/** Monthly TWR for the whole history, newest year first; never scrolls sideways. */
export function MonthlyReturns({ rows }: { rows: MonthReturns[] }) {
  const partial = rows.some((row) => row.first_partial_month !== null);
  return (
    <div className={styles.years}>
      {rows.map((row) => (
        <div key={row.year} className={styles.year} role="group" aria-label={`Rok ${row.year}`}>
          <div className={styles.yearHead}>
            <span>{row.year}</span>
            <span className={`num ${tone(row.year_pct)}`}>{formatPercent(row.year_pct, { places: 1 })}</span>
          </div>
          <ul className={styles.months}>
            {row.months.map((pct, i) => {
              const isPartial = row.first_partial_month === i + 1;
              return (
                <li key={MONTHS[i]} className={`${styles.month} ${isPartial ? styles.partial : ""}`}
                  style={{ background: cellBackground(pct) }}
                  aria-label={`${MONTHS[i]} ${row.year}${isPartial ? ", niepełny miesiąc" : ""}`}>
                  <span>{MONTHS[i]}</span>
                  {pct === null ? "–" : formatPercent(pct, { places: 1 })}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {partial && <p className={styles.legend}>Przerywana ramka to niepełny miesiąc na początku historii.</p>}
    </div>
  );
}
