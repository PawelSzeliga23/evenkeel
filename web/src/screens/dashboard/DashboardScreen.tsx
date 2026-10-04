import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Summary } from "../../api/types";
import { formatDayLong, formatRefreshed } from "../../format";
import { Logo } from "../../brand/Logo";
import { AddTileSheet } from "../../dashboard/AddTileSheet";
import { DashboardGrid, EditableGrid } from "../../dashboard/DashboardGrid";
import tiles from "../../dashboard/Dashboard.module.css";
import { DEFAULT_LAYOUT, MAX_TILES, addTile, newTileId, normalize, sameLayout, type DashboardLayout } from "../../dashboard/layout";
import { EditTilesIcon, EyeIcon, EyeOffIcon, RefreshIcon, SettingsIcon } from "../../shell/icons";
import { usePrivacy } from "../../settings/privacy";
import shell from "../../shell/shell.module.css";
import { AccountSelect, AccountsFailed } from "../../ui/AccountPicker";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import styles from "./Dashboard.module.css";
import { RECALC_POLL_MS } from "./model";
import { usePreferences, useSavePreferences } from "../../settings/preferences";
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
  // Editing (plan 9): `?edycja` in the address, so the sidebar's „Edytuj pulpit” opens it from any screen.
  const [params, setParams] = useSearchParams();
  const editing = params.has("edycja");
  const [draft, setDraft] = useState<DashboardLayout | null>(null);
  const [adding, setAdding] = useState(false);
  const [configuring, setConfiguring] = useState<string | null>(null);
  const save = useSavePreferences();
  const shown = editing ? (draft ?? layout) : layout;
  function stopEditing() {
    setDraft(null);
    setAdding(false);
    setConfiguring(null);
    setParams((current) => { current.delete("edycja"); return current; }, { replace: true });
  }
  function done() {
    // the default layout is saved as none, so a later change of the default reaches this owner too
    save.mutate({ dashboard: sameLayout(shown, DEFAULT_LAYOUT) ? null : shown }, { onSuccess: stopEditing });
  }

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
        <span>
          {!editing && (
            <button type="button" className={`${shell.gear} ${tiles.tileEditButton}`} aria-label="Edytuj pulpit"
              onClick={() => setParams({ edycja: "" })}><EditTilesIcon /></button>
          )}
          <Link className={shell.gear} to="/ustawienia" aria-label="Ustawienia"><SettingsIcon /></Link>
        </span>
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

  if (editing) {
    const full = shown.tiles.length >= MAX_TILES;
    return (
      <div className={ui.page}>
        <div className={tiles.tileEditBar} role="toolbar" aria-label="Edycja pulpitu">
          <button type="button" className={ui.primaryButton} disabled={full} onClick={() => setAdding(true)}>+ Dodaj kafelek</button>
          <button type="button" className={ui.secondary} onClick={() => { setDraft(DEFAULT_LAYOUT); setConfiguring(null); }}>
            Przywróć domyślny
          </button>
          <span className={tiles.tileEditEnd}>
            <button type="button" className={ui.secondary} onClick={stopEditing}>Anuluj</button>
            <button type="button" className={ui.primaryButton} disabled={save.isPending} onClick={done}>Gotowe</button>
          </span>
        </div>
        {full && <p className="dim">{`Pulpit ma już ${MAX_TILES} kafelków.`}</p>}
        {save.isError && <p role="alert" className={styles.refreshError}>Nie udało się zapisać układu. Spróbuj ponownie.</p>}
        {adding && (
          <AddTileSheet onClose={() => setAdding(false)} onAdd={(kind) => {
            const id = newTileId();
            setDraft(addTile(shown, kind, id));
            setAdding(false);
            // a price chart needs its holding first; other kinds start with their defaults
            setConfiguring(kind === "price_chart" ? id : null);
          }} />
        )}
        {shown.tiles.length === 0 && <p className="dim">Pulpit jest pusty — dodaj kafelek.</p>}
        <EditableGrid layout={shown} summary={data} onChange={setDraft} configuring={configuring} onConfigure={setConfiguring} />
      </div>
    );
  }

  return (
    <div className={ui.page}>
      {header}
      {recalculating && <Recalculating />}
      {layout.tiles.length === 0
        ? <EmptyState title="Pulpit jest pusty." action={<button type="button" className={ui.secondary}
          onClick={() => setParams({ edycja: "" })}>Dodaj kafelki</button>} />
        : <DashboardGrid layout={layout} summary={data} />}
    </div>
  );
}
