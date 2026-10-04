const box = { width: 23, height: 23, viewBox: "0 0 24 24", "aria-hidden": true } as const;
const line = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;

export const DashboardIcon = () => <svg {...box}><path {...line} d="M3 13h4v7H3zM10 8h4v12h-4zM17 4h4v16h-4z" /></svg>;
export const PositionsIcon = () => <svg {...box}><path {...line} d="M4 6h16M4 12h16M4 18h10" /></svg>;
export const AddIcon = () => <svg {...box} width={20} height={20}><path {...line} strokeWidth={2} d="M12 5v14M5 12h14" /></svg>;
export const HistoryIcon = () => <svg {...box}><circle {...line} cx="12" cy="12" r="8" /><path {...line} d="M12 8v4l3 2" /></svg>;
export const RefreshIcon = () => (
  <svg {...box} width={18} height={18}>
    <path {...line} strokeWidth={1.8} d="M20 12a8 8 0 1 1-2.34-5.66M20 4v4.5h-4.5" />
  </svg>
);
/** A cog: a toothed wheel around a hole (the old rays read as a sun). */
export const SettingsIcon = () => (
  <svg {...box}>
    <circle {...line} cx="12" cy="12" r="3" />
    <path {...line} d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);
export const AnalysisIcon = () => <svg {...box}><path {...line} d="M3 17l5-6 4 3 8-9" /><path {...line} d="M15 5h5v5" /></svg>;
export const EyeIcon = () => (
  <svg {...box} width={20} height={20}>
    <path {...line} d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle {...line} cx="12" cy="12" r="3" />
  </svg>
);
export const EyeOffIcon = () => (
  <svg {...box} width={20} height={20}>
    <path {...line} d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle {...line} cx="12" cy="12" r="3" />
    <path {...line} d="M4 4l16 16" />
  </svg>
);
