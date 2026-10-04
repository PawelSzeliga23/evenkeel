import { useId } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Limit } from "../../api/types";
import { formatMoney } from "../../format";
import ui from "../../ui/ui.module.css";
import styles from "./Limits.module.css";
import { WRAPPER_LABEL, byWrapper, filled, overBy } from "./model";

export function LimitBar({ limit }: { limit: Limit }) {
  const share = filled(limit);
  if (share === null) return null;
  return (
    <div className={`${styles.bar} ${limit.exceeded ? styles.over : ""}`} aria-hidden="true">
      <i style={{ width: `${(share * 100).toFixed(1)}%` }} />
    </div>
  );
}

function line(limit: Limit): string {
  const head = `${WRAPPER_LABEL[limit.wrapper]} ${limit.year}`;
  const over = overBy(limit);
  if (over !== null) return `${head}: przekroczono limit o ${formatMoney(over)}`;
  if (limit.limit_pln === null) return `${head}: ${formatMoney(limit.paid_pln)}, brak limitu w danych`;
  return `${head}: ${formatMoney(limit.paid_pln)} z ${formatMoney(limit.limit_pln)}`;
}

export function LimitsCard() {
  const titleId = useId(); // a tile of the Pulpit can show the card twice (plan 9)
  const limits = useQuery({ queryKey: keys.limits, queryFn: api.limits });
  if (!limits.data || limits.data.length === 0) return null;
  return (
    <section className={ui.section} aria-labelledby={titleId}>
      <div className={ui.sectionHead}>
        <h2 id={titleId} className={ui.sectionTitle}>Limity IKE/IKZE</h2>
        <Link className={ui.sectionMore} to="/limity" aria-label="Szczegóły limitów">Szczegóły</Link>
      </div>
      {byWrapper(limits.data).map(({ wrapper, current }) => (
        <div key={wrapper} className={styles.item}>
          <p className={current.exceeded ? "down" : ""}>{line(current)}</p>
          <LimitBar limit={current} />
        </div>
      ))}
    </section>
  );
}
