import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { AccountChips } from "../../ui/AccountPicker";
import { Money } from "../../ui/Amount";
import { ListRow } from "../../ui/ListRow";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { flagLabel, groupPositions, leadFor, positionLink, subtitleFor } from "./model";
import styles from "./Positions.module.css";

export function PositionsScreen() {
  const [accountId, setAccountId] = useState<number | null>(null);
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const positions = useQuery({ queryKey: keys.positions(accountId), queryFn: () => api.positions(accountId) });

  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Pozycje</h1>
      {(accounts.data?.length ?? 0) > 0 && <AccountChips accounts={accounts.data!} value={accountId} onChange={setAccountId} />}
      {positions.isPending ? <Skeleton rows={6} />
        : positions.isError ? <ErrorState error={positions.error} onRetry={() => void positions.refetch()} />
          : positions.data.length === 0 ? (
            <EmptyState
              title="Nie masz jeszcze pozycji. Wgraj eksport z XTB, żeby je zobaczyć."
              action={<Link className={ui.primaryButton} to="/dodaj/xtb">Wgraj pliki z XTB</Link>}
            />
          ) : groupPositions(positions.data).map((group) => (
            <section key={group.key} className={ui.section} aria-labelledby={`group-${group.key}`}>
              <div className={styles.groupHead}>
                <h2 id={`group-${group.key}`} className={styles.groupTitle}>{group.title}</h2>
                <Money value={group.total} />
              </div>
              <div>
                {group.items.map((p) => (
                  <ListRow
                    key={`${p.kind}-${p.account_id}-${p.instrument_id ?? p.bond_holding_id ?? p.savings_account_id ?? p.currency}`}
                    to={positionLink(p)}
                    lead={leadFor(p)}
                    title={p.name}
                    subtitle={
                      <>
                        {subtitleFor(p)}
                        {p.flags.length > 0 && <span className={`flag ${styles.flags}`}>{p.flags.map(flagLabel).join(", ")}</span>}
                      </>
                    }
                    value={<Money value={p.value_pln} />}
                    detail={p.kind === "cash" ? <span className="dim">—</span> : <Money value={p.unrealized_pln} sign tone />}
                  />
                ))}
              </div>
            </section>
          ))}
    </div>
  );
}
