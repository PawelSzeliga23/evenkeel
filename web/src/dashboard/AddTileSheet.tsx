/** Plan 9: the kinds of tiles to add, each with what it shows; plan 9b: each variant with its size on a computer. */
import styles from "./Dashboard.module.css";
import { KIND_ORDER, KINDS, dimensionOf, type Tile, type TileKind, type TileVariant } from "./layout";

export function AddTileSheet({ onAdd, onClose }: { onAdd: (kind: TileKind, variant: TileVariant) => void; onClose: () => void }) {
  return (
    <div className={styles.tileSheet} role="group" aria-label="Dodaj kafelek">
      <div className={styles.tileHead}>
        <b>Dodaj kafelek</b>
        <button type="button" className={styles.tileRetry} onClick={onClose}>Zamknij</button>
      </div>
      <div className={styles.tileKinds}>
        {KIND_ORDER.map((kind) => (
          <div key={kind} className={styles.tileKind}>
            <b>{KINDS[kind].name}</b>
            <small>{KINDS[kind].description}</small>
            <span className={styles.tileVariants}>
              {KINDS[kind].variants.map((variant) => {
                const dimension = dimensionOf({ id: "new", kind, variant, settings: KINDS[kind].defaults() } as Tile);
                return (
                  <button key={variant} type="button" className={styles.tileVariant}
                    aria-label={`${KINDS[kind].name} ${dimension}`} onClick={() => onAdd(kind, variant)}>
                    {dimension}
                  </button>
                );
              })}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
