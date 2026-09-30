import { useQuery } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/endpoints";
import { keys } from "../api/queryKeys";
import { normalizeSelection, readSelection, writeSelection } from "./selection";

type Selection = [ids: number[], setIds: (ids: readonly number[]) => void, ready: boolean];

const SelectionContext = createContext<Selection | null>(null);

/** One account choice for the whole signed-in app, remembered in this browser per user. */
export function AccountSelectionProvider({ userId, children }: { userId: number; children: ReactNode }) {
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const [stored, setStored] = useState(() => readSelection(userId));
  const known = useMemo(() => accounts.data?.map((account) => account.id) ?? null, [accounts.data]);
  const ids = useMemo(() => normalizeSelection(stored, known), [stored, known]);
  // A stored choice may name an account deleted meanwhile: wait for the list before asking the API with it.
  const ready = stored.length === 0 || known !== null || accounts.isError;
  const setIds = useCallback((next: readonly number[]) => {
    const clean = normalizeSelection(next, known);
    setStored(clean);
    writeSelection(userId, clean);
  }, [known, userId]);
  const value = useMemo<Selection>(() => [ids, setIds, ready], [ids, setIds, ready]);
  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>;
}

export function useAccountSelection(): Selection {
  const selection = useContext(SelectionContext);
  if (!selection) throw new Error("useAccountSelection needs AccountSelectionProvider");
  return selection;
}
