import { formatMoney, moneyParts, signOf } from "../format";
import styles from "./ui.module.css";

export function HeroAmount({ value, size = "l" }: { value: string; size?: "l" | "m" }) {
  const parts = moneyParts(value);
  return (
    <span className={`num ${styles.hero} ${size === "m" ? styles.heroM : ""}`}>
      {parts.sign}{parts.whole}
      <span className={styles.grosze} data-part="grosze">,{parts.grosze}</span>
      <span className={styles.currency}>zł</span>
    </span>
  );
}

export function Money({
  value, sign = false, tone = false, currency,
}: { value: string; sign?: boolean; tone?: boolean; currency?: string | null }) {
  const direction = tone ? signOf(value) : 0;
  const toneClass = direction > 0 ? "up" : direction < 0 ? "down" : "";
  return <span className={`num ${toneClass}`.trim()}>{formatMoney(value, { sign, currency })}</span>;
}
