/** Plan 9: the kinds of tiles to add, each with what it shows. */
import styles from "./Dashboard.module.css";
import { KIND_ORDER, KINDS, type TileKind } from "./layout";

export function AddTileSheet({ onAdd, onClose }: { onAdd: (kind: TileKind) => void; onClose: () => void }) {
  return (
    <div className={styles.tileSheet} role="group" aria-label="Dodaj kafelek">
      <div className={styles.tileHead}>
        <b>Dodaj kafelek</b>
        <button type="button" className={styles.tileRetry} onClick={onClose}>Zamknij</button>
      </div>
      <div className={styles.tileKinds}>
        {KIND_ORDER.map((kind) => (
          <button key={kind} type="button" className={styles.tileKind} onClick={() => onAdd(kind)}>
            <b>{KINDS[kind].name}</b>
            <small>{KINDS[kind].description}</small>
          </button>
        ))}
      </div>
    </div>
  );
}
