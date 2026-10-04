import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { setAmountsHidden } from "../format";

const KEY = "evenkeel.hideAmounts";
/** The control that switched the amounts: the screen is re-rendered under a new key, so focus goes back to it. */
let refocus: string | null = null;
export function takeRefocus(): string | null { const id = refocus; refocus = null; return id; }
export const PrivacyContext = createContext<[boolean, (hidden: boolean) => void]>([false, () => {}]);

function stored(): boolean {
  try { return localStorage.getItem(KEY) === "true"; } catch { return false; }
}

/** Hidden amounts (plan 8a), per browser. The format layer reads the flag, so it is set before children render. */
export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [hidden, setHidden] = useState(stored);
  setAmountsHidden(hidden);
  const set = useCallback((next: boolean) => {
    const active = document.activeElement;
    refocus = active instanceof HTMLElement && active.id ? active.id : null;
    setHidden(next);
    try { localStorage.setItem(KEY, String(next)); } catch { /* storage unavailable: lasts this visit */ }
  }, []);
  const value = useMemo<[boolean, (hidden: boolean) => void]>(() => [hidden, set], [hidden, set]);
  return <PrivacyContext.Provider value={value}>{children}</PrivacyContext.Provider>;
}

export const usePrivacy = () => useContext(PrivacyContext);
