import { useEffect, useState } from "react";

/** Follows the element's width; jsdom has no ResizeObserver, so tests draw at `initial`. */
export function useWidth(element: HTMLElement | null, initial: number): number {
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const measured = Math.round(entry!.contentRect.width);
      if (measured > 0) setWidth(measured);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);
  return width;
}
