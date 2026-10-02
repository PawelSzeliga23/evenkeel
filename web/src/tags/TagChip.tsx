import type { CSSProperties } from "react";
import type { Tag, TagOn } from "../api/types";
import styles from "./Tags.module.css";

/** A tag's colour dot and name; dashed when it is only on this account, with „✕” when it can be taken off. */
export function TagChip({ tag, own = false, onRemove }: { tag: Tag | TagOn; own?: boolean; onRemove?: () => void }) {
  return (
    <span className={styles.chip} data-own={own ? "true" : "false"} style={{ "--tag": tag.color } as CSSProperties}>
      <i className={styles.dot} aria-hidden="true" />
      <span>{tag.name}</span>
      {onRemove && (
        <button type="button" className={styles.remove} aria-label={`Usuń tag ${tag.name}`} onClick={onRemove}>✕</button>
      )}
    </span>
  );
}
