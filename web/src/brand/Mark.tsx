import { useId } from "react";

export const BARS = [
  { x: 11, height: 12, opacity: 0.55 },
  { x: 22, height: 19, opacity: 0.7 },
  { x: 33, height: 25, opacity: 0.85 },
  { x: 44, height: 38, opacity: 1 },
] as const;
const BASE_Y = 52;

/** The Evenkeel mark: four rising amber bars on a dark tile. */
export function Mark({ size, className }: { size: number; className?: string }) {
  const id = useId();
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${id}t`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#1C2129" /><stop offset="1" stopColor="#0E1116" /></linearGradient>
        <linearGradient id={`${id}b`} x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor="#8A5A1C" /><stop offset="1" stopColor="#FFC266" /></linearGradient>
      </defs>
      <rect x="0.5" y="0.5" width="63" height="63" rx="15" fill={`url(#${id}t)`} stroke="#242A33" />
      {BARS.map((bar) => (
        <rect key={bar.x} data-bar="" x={bar.x} y={BASE_Y - bar.height} width="8" height={bar.height} rx="1.5"
          fill={`url(#${id}b)`} opacity={bar.opacity} />
      ))}
      <line x1="8" y1={BASE_Y} x2="56" y2={BASE_Y} stroke="#3A424E" strokeWidth="1.5" />
    </svg>
  );
}
