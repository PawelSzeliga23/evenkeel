import { Link } from "react-router";
import styles from "./ui.module.css";

export function BackLink({ to, label }: { to: string; label: string }) {
  return (
    <Link className={styles.back} to={to}>
      <svg width="10" height="14" viewBox="0 0 10 14" aria-hidden="true">
        <path d="M8 1 2 7l6 6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      {label}
    </Link>
  );
}
