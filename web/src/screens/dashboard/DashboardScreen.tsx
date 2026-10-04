import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";
import { Link, useLocation } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Summary } from "../../api/types";
import { formatDayLong, formatRefreshed } from "../../format";
import { Logo } from "../../brand/Logo";
import { DashboardGrid } from "../../dashboard/DashboardGrid";
import { DEFAULT_LAYOUT, normalize, type DashboardLayout } from "../../dashboard/layout";
import { EyeIcon, EyeOffIcon, RefreshIcon, SettingsIcon } from "../../shell/icons";
import { usePrivacy } from "../../settings/privacy";
import shell from "../../shell/shell.module.css";
import { AccountSelect, AccountsFailed } from "../../ui/AccountPicker";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import styles from "./Dashboard.module.css";
import { RECALC_POLL_MS } from "./model";
import { usePreferences } from "../../settings/preferences";
import type { Preferences } from "../../api/types";

/** The saved layout; without one, today's Pulpit with the default chart range from Ustawienia (plan 8a). */
export function layoutOf(prefs: Preferences): DashboardLayout {
  if (prefs.dashboard !== null && prefs.dashboard !== undefined) return normalize(prefs.dashboard);
  return {
    ...DEFAULT_LAYOUT,
    tiles: DEFAULT_LAYOUT.tiles.map((t) => (t.kind === "value_chart" ? { ...t, settings: { range: prefs.value_range } } : t)),
  };
}

export function DashboardScreen() {
  const queryClient = useQueryClient();
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  const notice = (useLocation().state as { notice?: string } | null)?.notice; // e.g. after restoring a backup
  const [hidden, setHidden] = usePrivacy();
  const prefs = usePreferences();
  const layout = useMemo(() => layoutOf(prefs), [prefs]);

  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const summary = useQuery({
    queryKey: keys.summary(accountIds),
    queryFn: () => api.summary(accountIds),
    enabled: ready,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
    placeholderData: (previous) => previous,
  });
  const asOf = summary.data?.as_of ?? null;

  // When the background recalculation ends, everything valued may have changed.
  const recalculating = summary.data?.recalculating ?? false;
  const wasRecalculating = useRef(false);
  useEffect(() => {
    if (wasRecalculating.current && !recalculating) {
      void queryClient.invalidateQueries({ queryKey: keys.portfolio, predicate: (q) => q.queryKey[1] !== "summary" });
    }
    wasRecalculating.current = recalculating;
  }, [recalculating, queryClient]);

  // Fetch current prices now; the summary then reports the recalculation and the rest follows as above.
  const refresh = useMutation({
    mutationFn: api.refreshPrices,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.portfolio }),
  });
  const refreshedAt = summary.data?.prices_refreshed_at ?? null;

  const header = (
    <>
      <div className={`${shell.phoneOnly} ${shell.topRow}`}>
        <Logo layout="inline" markSize={24} />
        <Link className={shell.gear} to="/ustawienia" aria-label="Ustawienia"><SettingsIcon /></Link>
      </div>
      <div className={styles.bar}>
        {accounts.data ? <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />
          : accounts.isError ? <AccountsFailed onRetry={() => void accounts.refetch()} /> : <span />}
        <span className={styles.refreshed}>
          {refreshedAt ? (
            <>
              <span className="dim">{formatRefreshed(refreshedAt)}</span>
              <button type="button" className={styles.refresh} aria-label="Odśwież ceny" disabled={refresh.isPending}
                data-spinning={refresh.isPending || recalculating} onClick={() => refresh.mutate()}>
                <RefreshIcon />
              </button>
            </>
          ) : asOf && <span className="dim">{formatDayLong(asOf)}</span>}
          <button id="privacy-eye" type="button" className={styles.refresh} aria-label={hidden ? "Pokaż kwoty" : "Ukryj kwoty"}
            aria-pressed={hidden} onClick={() => setHidden(!hidden)}>
            {hidden ? <EyeOffIcon /> : <EyeIcon />}
          </button>
        </span>
      </div>
      {notice && <p className={ui.notice} role="status">{notice}</p>}
      {refresh.isError && <p role="alert" className={styles.refreshError}>Nie udało się odświeżyć cen. Spróbuj ponownie.</p>}
    </>
  );

  if (summary.isPending) return <div className={ui.page}>{header}<Skeleton chart rows={4} /></div>;
  if (summary.isError) return <div className={ui.page}>{header}<ErrorState error={summary.error} onRetry={() => void summary.refetch()} /></div>;

  const data: Summary = summary.data;
  if (asOf === null) {
    return (
      <div className={ui.page}>
        {header}
        {recalculating ? <><Recalculating /><Skeleton chart rows={3} /></> : accountIds.length > 0 ? (
          <EmptyState
            title="Wybrane konta nie mają jeszcze wyceny."
            action={<button type="button" className={ui.secondary} onClick={() => setAccountIds([])}>Pokaż cały portfel</button>}
          />
        ) : (
          <EmptyState
            title="Wgraj eksport z XTB, żeby zobaczyć swój portfel."
            action={<Link className={ui.primaryButton} to="/dodaj/xtb">Wgraj pliki z XTB</Link>}
          />
        )}
      </div>
    );
  }

  return (
    <div className={ui.page}>
      {header}
      {recalculating && <Recalculating />}
      <DashboardGrid layout={layout} summary={data} />
    </div>
  );
}
