import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { setAmountsHidden } from "../format";

const KEY = "evenkeel.hideAmounts";
export const PrivacyContext = createContext<[boolean, (hidden: boolean) => void]>([false, () => {}]);

function stored(): boolean {
  try { return localStorage.getItem(KEY) === "true"; } catch { return false; }
}

/** Hidden amounts (plan 8a), per browser. The format layer reads the flag, so it is set before children render. */
export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [hidden, setHidden] = useState(stored);
  setAmountsHidden(hidden);
  const set = useCallback((next: boolean) => {
    setHidden(next);
    try { localStorage.setItem(KEY, String(next)); } catch { /* storage unavailable: lasts this visit */ }
  }, []);
  const value = useMemo<[boolean, (hidden: boolean) => void]>(() => [hidden, set], [hidden, set]);
  return <PrivacyContext.Provider value={value}>{children}</PrivacyContext.Provider>;
}

export const usePrivacy = () => useContext(PrivacyContext);
