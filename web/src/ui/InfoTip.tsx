import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import type { Help } from "./help";
import styles from "./InfoTip.module.css";

const WIDTH = 260;
const GUTTER = 16;
const GAP = 6;

/** A "?" that explains a measure. A mouse opens it by hovering; a tap (or Enter/Space) pins it open until a second
 * tap, Esc, a tap elsewhere or scrolling. The bubble is fixed to the viewport, stays 16 px inside its sides and opens
 * above the button when there is no room below it. */
export function InfoTip({ label, help }: { label: string; help: Help }) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const bubble = useRef<HTMLSpanElement>(null);
  const [pinned, setPinned] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [place, setPlace] = useState<CSSProperties>({});
  const open = pinned || hovered;

  // Measured before paint, so the bubble never shows unplaced; its height is read at its final width.
  useLayoutEffect(() => {
    if (!open || !button.current || !bubble.current) return;
    const rect = button.current.getBoundingClientRect();
    const width = Math.min(WIDTH, window.innerWidth - 2 * GUTTER);
    const left = Math.min(Math.max(rect.right - width, GUTTER), window.innerWidth - GUTTER - width);
    bubble.current.style.width = `${width}px`;
    const height = bubble.current.offsetHeight;
    const below = rect.bottom + GAP;
    const top = below + height > window.innerHeight - GUTTER ? Math.max(rect.top - GAP - height, GUTTER) : below;
    setPlace({ top, left, width });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = () => { setPinned(false); setHovered(false); };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    const onDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!button.current?.contains(target) && !bubble.current?.contains(target)) close(); // reading the bubble keeps it
    };
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
        <span ref={bubble} role="tooltip" id={id} className={styles.bubble} style={place}>
          {help.what}
          <span className={styles.how}>Jak liczymy: {help.how}</span>
        </span>
      )}
    </span>
  );
}
