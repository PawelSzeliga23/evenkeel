import { useQuery } from "@tanstack/react-query";
import { useState, type CSSProperties } from "react";
import { Link, useSearchParams } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Position } from "../../api/types";
import { TagChip } from "../../tags/TagChip";
import tagStyles from "../../tags/Tags.module.css";
import { AccountSelect } from "../../ui/AccountPicker";
import { Money } from "../../ui/Amount";
import { ListRow } from "../../ui/ListRow";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { ClosedView } from "./ClosedView";
import { flagLabel, groupByTag, groupPositions, leadFor, positionLink, subtitleFor, type TagGroup } from "./model";
import styles from "./Positions.module.css";

type Grouping = "kind" | "tag";
const GROUPING_KEY = "evenkeel.positions.grouping";

function storedGrouping(): Grouping {
  try { return localStorage.getItem(GROUPING_KEY) === "tag" ? "tag" : "kind"; } catch { return "kind"; }
}

function useGrouping(): [Grouping, (next: Grouping) => void] {
  const [grouping, setGrouping] = useState<Grouping>(storedGrouping);
  return [grouping, (next) => {
    setGrouping(next);
    try { localStorage.setItem(GROUPING_KEY, next); } catch { /* storage unavailable: the choice lasts this visit */ }
  }];
}

function groups(positions: Position[], grouping: Grouping): TagGroup[] {
  return grouping === "tag" ? groupByTag(positions) : groupPositions(positions).map((g) => ({ ...g, color: null }));
}

function Row({ p }: { p: Position }) {
  return (
    <ListRow
      to={positionLink(p)}
      lead={leadFor(p)}
      title={p.name}
      subtitle={
        <>
          {subtitleFor(p)}
          {p.flags.length > 0 && <span className={`flag ${styles.flags}`}>{p.flags.map(flagLabel).join(", ")}</span>}
          {p.tags.length > 0 && (
            <span className={`${tagStyles.chips} ${styles.rowTags}`}>
              {p.tags.map((tag) => <TagChip key={tag.link_id} tag={tag} own={tag.own} />)}
            </span>
          )}
        </>
      }
      value={<Money value={p.payout_pln} />}
      detail={p.kind === "cash" ? <span className="dim">—</span> : <Money value={p.unrealized_pln} sign tone />}
    />
  );
}

export function PositionsScreen() {
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  const [params, setParams] = useSearchParams();
  const [grouping, setGrouping] = useGrouping();
  const view = params.get("widok") === "zamkniete" ? "closed" : "open";
  const setView = (next: "open" | "closed") => setParams(next === "closed" ? { widok: "zamkniete" } : {}, { replace: true });
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const positions = useQuery({ queryKey: keys.positions(accountIds), queryFn: () => api.positions(accountIds), enabled: ready && view === "open" });

  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Pozycje</h1>
      {(accounts.data?.length ?? 0) > 0 && <AccountSelect accounts={accounts.data!} value={accountIds} onChange={setAccountIds} />}
      <Segmented label="Widok pozycji" value={view} onChange={setView}
        options={[{ value: "open", label: "Otwarte" }, { value: "closed", label: "Zamknięte" }]} />
      {view === "open" && (
        <Segmented label="Grupowanie pozycji" value={grouping} onChange={setGrouping}
          options={[{ value: "kind", label: "Grupuj: rodzaj" }, { value: "tag", label: "Grupuj: tag" }]} />
      )}
      {view === "closed" ? <ClosedView accountIds={accountIds} ready={ready} /> : (
        positions.isPending ? <Skeleton rows={6} />
        : positions.isError ? <ErrorState error={positions.error} onRetry={() => void positions.refetch()} />
          : positions.data.length === 0 ? (
            <EmptyState
              title="Nie masz jeszcze pozycji. Wgraj eksport z XTB, żeby je zobaczyć."
              action={<Link className={ui.primaryButton} to="/dodaj/xtb">Wgraj pliki z XTB</Link>}
            />
          ) : groups(positions.data, grouping).map((group) => (
            <section key={group.key} className={ui.section} aria-labelledby={`group-${group.key}`}>
              <div className={styles.groupHead}>
                <h2 id={`group-${group.key}`} className={styles.groupTitle}>
                  {group.color && (
                    <i className={`${tagStyles.dot} ${styles.groupDot}`} aria-hidden="true"
                      style={{ "--tag": group.color } as CSSProperties} />
                  )}
                  {group.title}
                </h2>
                <Money value={group.total} />
              </div>
              <div>
                {group.items.map((p) => (
                  <Row key={`${p.kind}-${p.account_id}-${p.instrument_id ?? p.bond_holding_id ?? p.savings_account_id ?? p.currency}`} p={p} />
                ))}
              </div>
            </section>
          ))
      )}
    </div>
  );
}
