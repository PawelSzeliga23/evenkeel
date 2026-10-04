import { useMutation } from "@tanstack/react-query";
import { useMemo } from "react";
import { api } from "../api/endpoints";
import type { Preferences } from "../api/types";
import { useSession } from "../auth/session";

export const DEFAULT_PREFERENCES: Preferences = {
  start_screen: "dashboard", accounts_start: "last", accounts_fixed: [], analysis_period: "all",
  holdings_period: "all", value_range: "1R", price_range: "buy", holdings_without_fixed_income: false,
};

/** The signed-in owner's preferences over the defaults; the defaults before sign-in. */
export function usePreferences(): Preferences {
  const { state } = useSession();
  const stored = state.status === "signedIn" ? state.user.preferences : undefined;
  return useMemo(() => ({ ...DEFAULT_PREFERENCES, ...stored }), [stored]);
}

export function useSavePreferences() {
  const { setPreferences } = useSession();
  return useMutation({
    mutationFn: (patch: Partial<Preferences>) => api.savePreferences(patch),
    onSuccess: (saved) => setPreferences(saved),
  });
}
