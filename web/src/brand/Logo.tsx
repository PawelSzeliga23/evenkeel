import styles from "./brand.module.css";
import { Mark } from "./Mark";

export const APP_NAME = "Evenkeel";

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={className ? `${styles.word} ${className}` : styles.word}>
      Even<span data-part="keel" className={styles.keel}>keel</span>
    </span>
  );
}

/** The mark with the name under it (stacked) or next to it (inline). */
export function Logo({ layout, markSize = layout === "stacked" ? 72 : 28 }: { layout: "stacked" | "inline"; markSize?: number }) {
  return (
    <span role="img" aria-label={APP_NAME} data-layout={layout} className={styles[layout]}>
      <Mark size={markSize} />
      <Wordmark className={layout === "inline" ? styles.small : undefined} />
    </span>
  );
}
