import { useState } from "react";
import type { Holding, HoldingsPeriod } from "../../api/types";
import { heatColor, squarify } from "../../charts/treemap";
import { useWidth } from "../../charts/useWidth";
import { formatPercent, signOf } from "../../format";
import { shortTicker } from "../../ui/ticker";
import styles from "./Holdings.module.css";

const DEFAULT_W = 340;
/** Below these a tile shows no label (it still opens its details). */
const LABEL_W = 44;
const LABEL_H = 30;
const PCT_H = 44;

export const holdingLabel = (item: Holding) => (item.ticker ? shortTicker(item.ticker) : item.name);

/** Holdings as tiles: size by value, colour by the period's gain %. */
export function HeatMap({ items, period, selected, onSelect, height = 220 }: {
  items: Holding[]; period: HoldingsPeriod; selected: string | null; onSelect: (key: string) => void; height?: number;
}) {
  const [box, setBox] = useState<HTMLElement | null>(null);
  const width = useWidth(box, DEFAULT_W);
  const shown = items.filter((item) => signOf(item.value_pln) > 0);
  const rects = squarify(shown.map((item) => Number(item.value_pln)), width, height);
  return (
    <div ref={setBox} className={styles.map} style={{ height }} role="group" aria-label="Mapa walorów">
      {shown.map((item, i) => {
        const r = rects[i]!;
        const label = holdingLabel(item);
        const pct = formatPercent(item.gain_pct);
        return (
          <button key={item.key} type="button" className={styles.tile} aria-pressed={item.key === selected}
            aria-label={`${label}, ${pct}`} onClick={() => onSelect(item.key)}
            style={{ left: r.x, top: r.y, width: r.w, height: r.h, background: heatColor(item.gain_pct, period) }}>
            {r.w >= LABEL_W && r.h >= LABEL_H && (
              <span aria-hidden="true">
                <b>{label}</b>
                {r.h >= PCT_H && <small>{pct}</small>}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
