import type { ReactNode } from "react";
import { errorMessage } from "../api/messages";
import styles from "./ui.module.css";

export function Skeleton({ rows = 3, chart = false }: { rows?: number; chart?: boolean }) {
  return (
    <div className={styles.skeleton} aria-busy="true" aria-label="Wczytuję">
      {chart && <div className={styles.skeletonChart} />}
      {Array.from({ length: rows }, (_, i) => <div key={i} className={styles.skeletonRow} />)}
    </div>
  );
}

export function EmptyState({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className={styles.empty}>
      <p>{title}</p>
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className={styles.errorBox}>
      <p role="alert">{errorMessage(error)}</p>
      {onRetry && <button type="button" className={styles.secondary} onClick={onRetry}>Spróbuj ponownie</button>}
    </div>
  );
}

export function Recalculating() {
  return <p className={styles.recalculating} role="status">Przeliczam wycenę…</p>;
}
