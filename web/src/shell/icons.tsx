const box = { width: 23, height: 23, viewBox: "0 0 24 24", "aria-hidden": true } as const;
const line = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;

export const DashboardIcon = () => <svg {...box}><path {...line} d="M3 13h4v7H3zM10 8h4v12h-4zM17 4h4v16h-4z" /></svg>;
export const PositionsIcon = () => <svg {...box}><path {...line} d="M4 6h16M4 12h16M4 18h10" /></svg>;
export const AddIcon = () => <svg {...box} width={20} height={20}><path {...line} strokeWidth={2} d="M12 5v14M5 12h14" /></svg>;
export const HistoryIcon = () => <svg {...box}><circle {...line} cx="12" cy="12" r="8" /><path {...line} d="M12 8v4l3 2" /></svg>;
export const SettingsIcon = () => (
  <svg {...box}>
    <circle {...line} cx="12" cy="12" r="3" />
    <path {...line} d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8" />
  </svg>
);
