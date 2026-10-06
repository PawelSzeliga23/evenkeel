import { useEffect, useRef, useState, type PointerEvent } from "react";
import type { Frame } from "./geometry";
import { moveWindow, scaleRange, shiftRange, type ChartWindow, type YRange } from "./viewport";

const HINT_MS = 1500;
const WHEEL_SPEED = 0.0015;
const AXIS_SPEED = 0.01;
const DRAG_START_PX = 3;
const TAP_MS = 300;
const TAP_MOVE_PX = 10;
const HOLD_MS = 400;

interface Options {
  view: ChartWindow;
  count: number;
  frame: Frame;
  /** The amounts on screen now, automatic or hand-set. */
  y(): YRange;
  /** True when the owner has set the amounts by hand; then a drag moves them up and down too. */
  manualY: boolean;
  /** False on a chart without a hand-set scale: its amounts axis then pans and scrolls like the rest. */
  scaleY?: boolean;
  onChange(view: ChartWindow): void;
  onYChange(range: YRange): void;
  onReset(): void;
  /** A finger held still for a moment: show the day at `x` (frame units); the finger then slides along the days. */
  onHold?(x: number): void;
}
interface Gesture {
  kind: "drag" | "pinch" | "scale" | "inspect";
  touch: boolean;
  view: ChartWindow;
  y: YRange;
  manualY: boolean;
  frac: number;
  dist: number;
  startX: number;
  startY: number;
  moved: boolean;
}
interface Touch { time: number; x: number; y: number }
type Spot = { x: number; y: number };

/** Frame units per CSS pixel (the SVG is drawn at its measured width, so this is about 1). */
function unitsPerPx(target: Element, frame: Frame): number {
  const rect = target.getBoundingClientRect();
  return rect.width ? frame.width / rect.width : 1;
}

/** Share of the plot width under `clientX`, 0 at the left edge, 1 at the right. */
function fracAt(target: Element, clientX: number, frame: Frame): number {
  const rect = target.getBoundingClientRect();
  if (!rect.width) return 0.5;
  const px = ((clientX - rect.left) / rect.width) * frame.width;
  return Math.min(Math.max((px - frame.left) / (frame.width - frame.left - frame.right), 0), 1);
}

function onYAxis(target: Element, clientX: number, frame: Frame): boolean {
  const rect = target.getBoundingClientRect();
  return rect.width > 0 && ((clientX - rect.left) / rect.width) * frame.width > frame.width - frame.right;
}

/** Where `clientX` falls on the frame, in frame units. */
function frameX(target: Element, clientX: number, frame: Frame): number {
  const rect = target.getBoundingClientRect();
  return rect.width ? ((clientX - rect.left) / rect.width) * frame.width : 0;
}

/**
 * Ctrl + wheel and pinch zoom, a drag (mouse, or one finger sideways) and two-finger pan, a drag on the Y axis
 * scales the amounts, a finger held still shows the day, double click or tap resets.
 */
export function useChartGestures(options: Options) {
  const latest = useRef(options);
  latest.current = options;
  const [svg, setSvg] = useState<SVGSVGElement | null>(null);
  const [hint, setHint] = useState(false);
  const pointers = useRef(new Map<number, Spot>());
  const gesture = useRef<Gesture | null>(null);
  const down = useRef<Touch | null>(null);
  const lastTap = useRef<Touch | null>(null);
  const hold = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(hold.current), []);

  // React's onWheel is passive, so preventDefault (keep the page still while zooming) needs a native listener.
  useEffect(() => {
    if (!svg) return;
    const target = svg;
    let timer: number | undefined;
    function onWheel(event: WheelEvent) {
      if (!event.ctrlKey) {
        setHint(true);
        window.clearTimeout(timer);
        timer = window.setTimeout(() => setHint(false), HINT_MS);
        return;
      }
      event.preventDefault();
      const { view, count, frame, onChange } = latest.current;
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : 1);
      const frac = fracAt(target, event.clientX, frame);
      onChange(moveWindow(view, frac, frac, Math.exp(delta * WHEEL_SPEED), count));
    }
    // The chart keeps `touch-action: pan-y` so a finger can still scroll the page; once a gesture of the chart is
    // under way (two fingers, the amounts axis, a held finger) the page must stay still or the browser cancels it.
    function onTouchMove(event: TouchEvent) {
      const kind = gesture.current?.kind;
      if (event.cancelable && (event.touches.length > 1 || kind === "scale" || kind === "inspect" || kind === "pinch")) {
        event.preventDefault();
      }
    }
    target.addEventListener("wheel", onWheel, { passive: false });
    target.addEventListener("touchmove", onTouchMove, { passive: false });
    return () => {
      target.removeEventListener("wheel", onWheel);
      target.removeEventListener("touchmove", onTouchMove);
      window.clearTimeout(timer);
    };
  }, [svg]);

  function onPointerDown(event: PointerEvent<SVGSVGElement>): boolean {
    const { view, frame, y, manualY, scaleY = true } = latest.current;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const base = {
      view, y: y(), manualY, dist: 1, startX: event.clientX, startY: event.clientY, moved: false,
      touch: event.pointerType !== "mouse",
    };
    window.clearTimeout(hold.current);
    if (event.pointerType === "mouse") {
      if (event.button !== 0) return false;
      try {
        event.currentTarget.setPointerCapture?.(event.pointerId);
      } catch {
        // Capture only keeps the drag alive outside the chart; without it the drag still works inside.
      }
      const scale = scaleY && onYAxis(event.currentTarget, event.clientX, frame);
      gesture.current = { ...base, kind: scale ? "scale" : "drag", frac: fracAt(event.currentTarget, event.clientX, frame) };
      return scale;
    }
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()] as [Spot, Spot];
      gesture.current = {
        ...base, kind: "pinch", frac: fracAt(event.currentTarget, (a.x + b.x) / 2, frame),
        dist: Math.max(Math.hypot(a.x - b.x, a.y - b.y), 1), startX: (a.x + b.x) / 2, moved: true,
      };
      down.current = null;
      return true;
    }
    if (pointers.current.size > 2) return true;
    down.current = { time: event.timeStamp, x: event.clientX, y: event.clientY };
    const target = event.currentTarget;
    const scale = scaleY && onYAxis(target, event.clientX, frame);
    const started: Gesture = { ...base, kind: scale ? "scale" : "drag", frac: fracAt(target, event.clientX, frame) };
    gesture.current = started;
    if (!scale) {
      hold.current = window.setTimeout(() => {
        if (gesture.current !== started || started.moved) return;
        started.kind = "inspect";
        down.current = null;
        latest.current.onHold?.(frameX(target, started.startX, latest.current.frame));
      }, HOLD_MS);
    }
    return true;
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>): boolean {
    if (!pointers.current.has(event.pointerId)) return false;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const current = gesture.current;
    if (!current) return event.pointerType !== "mouse";
    const { count, frame, onChange, onYChange } = latest.current;
    if (current.kind === "inspect") return false;
    if (current.kind !== "pinch") {
      const moved = Math.hypot(event.clientX - current.startX, event.clientY - current.startY);
      if (!current.moved && moved < (current.touch ? TAP_MOVE_PX : DRAG_START_PX)) return current.touch || current.kind === "scale";
      current.moved = true;
      window.clearTimeout(hold.current);
      const dy = (event.clientY - current.startY) * unitsPerPx(event.currentTarget, frame);
      if (current.kind === "scale") {
        onYChange(scaleRange(current.y, Math.exp(dy * AXIS_SPEED)));
        return true;
      }
      onChange(moveWindow(current.view, current.frac, fracAt(event.currentTarget, event.clientX, frame), 1, count));
      // A finger's up and down belongs to the page, so only the mouse moves a hand-set scale.
      if (current.manualY && !current.touch) {
        const plotHeight = frame.height - frame.top - frame.bottom;
        onYChange(shiftRange(current.y, (dy / plotHeight) * (current.y.max - current.y.min)));
      }
      return true;
    }
    if (pointers.current.size < 2) return true;
    const [a, b] = [...pointers.current.values()] as [Spot, Spot];
    const dist = Math.max(Math.hypot(a.x - b.x, a.y - b.y), 1);
    onChange(moveWindow(current.view, current.frac, fracAt(event.currentTarget, (a.x + b.x) / 2, frame), current.dist / dist, count));
    return true;
  }

  function onPointerUp(event: PointerEvent<SVGSVGElement>): void {
    pointers.current.delete(event.pointerId);
    gesture.current = null;
    window.clearTimeout(hold.current);
    const start = down.current;
    down.current = null;
    if (event.pointerType === "mouse" || event.type !== "pointerup" || !start) return;
    const isTap = event.timeStamp - start.time < TAP_MS && Math.hypot(event.clientX - start.x, event.clientY - start.y) < TAP_MOVE_PX;
    const previous = lastTap.current;
    if (isTap && previous && event.timeStamp - previous.time < TAP_MS && Math.hypot(event.clientX - previous.x, event.clientY - previous.y) < 30) {
      lastTap.current = null;
      latest.current.onReset();
      return;
    }
    lastTap.current = isTap ? { time: event.timeStamp, x: event.clientX, y: event.clientY } : null;
  }

  return { ref: setSvg, hint, onPointerDown, onPointerMove, onPointerUp, onDoubleClick: () => latest.current.onReset() };
}
