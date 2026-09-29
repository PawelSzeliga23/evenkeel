import type { ReactNode } from "react";
import { Link } from "react-router";
import styles from "./ui.module.css";

export function ListRow({
  lead, title, subtitle, value, detail, to,
}: { lead: ReactNode; title: ReactNode; subtitle?: ReactNode; value: ReactNode; detail?: ReactNode; to?: string }) {
  const body = (
    <>
      <span className={styles.lead}>{lead}</span>
      <span className={styles.rowName}>
        <b>{title}</b>
        {subtitle && <small>{subtitle}</small>}
      </span>
      <span className={styles.rowAmount}>
        <span>{value}</span>
        {detail && <small>{detail}</small>}
      </span>
    </>
  );
  return to ? <Link className={styles.row} to={to}>{body}</Link> : <div className={styles.row}>{body}</div>;
}
