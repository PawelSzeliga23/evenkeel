import { useEffect, useId, useRef, useState, type CSSProperties } from "react";
import type { Help } from "./help";
import styles from "./InfoTip.module.css";

const WIDTH = 260;
const GUTTER = 16;

/** A "?" that explains a measure. A mouse opens it by hovering; a tap (or Enter/Space) pins it open until a second
 * tap, Esc, a tap elsewhere or scrolling. The bubble is fixed to the viewport and stays 16 px inside its edges. */
export function InfoTip({ label, help }: { label: string; help: Help }) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const [pinned, setPinned] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [place, setPlace] = useState<CSSProperties>({});
  const open = pinned || hovered;

  useEffect(() => {
    if (!open || !button.current) return;
    const rect = button.current.getBoundingClientRect();
    const width = Math.min(WIDTH, window.innerWidth - 2 * GUTTER);
    const left = Math.min(Math.max(rect.right - width, GUTTER), window.innerWidth - GUTTER - width);
    setPlace({ top: rect.bottom + 6, left, width });
    const close = () => { setPinned(false); setHovered(false); };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    const onDown = (event: PointerEvent) => { if (!button.current?.contains(event.target as Node)) close(); };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("scroll", close, true);
    };
  }, [open]);

  return (
    <span className={styles.wrap}>
      <button ref={button} type="button" className={styles.button} aria-label={`Co to jest: ${label}`}
        aria-expanded={open} aria-describedby={open ? id : undefined}
        onClick={() => { setPinned(!pinned); setHovered(false); }}
        onPointerEnter={(event) => { if (event.pointerType === "mouse") setHovered(true); }}
        onPointerLeave={(event) => { if (event.pointerType === "mouse") setHovered(false); }}>
        ?
      </button>
      {open && (
        <span role="tooltip" id={id} className={styles.bubble} style={place}>
          {help.what}
          <span className={styles.how}>Jak liczymy: {help.how}</span>
        </span>
      )}
    </span>
  );
}
