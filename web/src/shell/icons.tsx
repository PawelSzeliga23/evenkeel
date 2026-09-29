const box = { width: 23, height: 23, viewBox: "0 0 24 24", "aria-hidden": true } as const;
const line = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;

export const DashboardIcon = () => <svg {...box}><path {...line} d="M3 13h4v7H3zM10 8h4v12h-4zM17 4h4v16h-4z" /></svg>;
export const PositionsIcon = () => <svg {...box}><path {...line} d="M4 6h16M4 12h16M4 18h10" /></svg>;
export const AddIcon = () => <svg {...box} width={20} height={20}><path {...line} strokeWidth={2} d="M12 5v14M5 12h14" /></svg>;
export const HistoryIcon = () => <svg {...box}><circle {...line} cx="12" cy="12" r="8" /><path {...line} d="M12 8v4l3 2" /></svg>;
export const MoreIcon = () => (
  <svg {...box}>
    <circle cx="6" cy="12" r="1.6" fill="currentColor" />
    <circle cx="12" cy="12" r="1.6" fill="currentColor" />
    <circle cx="18" cy="12" r="1.6" fill="currentColor" />
  </svg>
);
