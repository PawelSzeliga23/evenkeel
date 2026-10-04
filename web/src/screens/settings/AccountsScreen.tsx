import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { BackLink } from "../../ui/BackLink";
import { ListRow } from "../../ui/ListRow";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { ACCOUNT_KIND, WRAPPER } from "./model";
import styles from "./Settings.module.css";

/** Ustawienia → Konta: every account, each opening its own settings. */
export function AccountsScreen() {
  const notice = (useLocation().state as { notice?: string } | null)?.notice;
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <h1 className={ui.pageTitle}>Konta</h1>
      {notice && <p className={ui.notice} role="status">{notice}</p>}
      {accounts.isPending ? <Skeleton rows={2} />
        : accounts.isError ? <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
        : accounts.data.length === 0
          ? <p className="dim">Nie masz jeszcze kont. Powstają przy imporcie z XTB i przy dodaniu obligacji albo konta oszczędnościowego.</p>
          : (
            <div className={styles.list}>
              {accounts.data.map((account) => (
                <ListRow key={account.id} lead={account.name.slice(0, 2).toUpperCase()} title={account.name}
                  subtitle={ACCOUNT_KIND[account.kind]} value={WRAPPER[account.wrapper]} to={`/ustawienia/konta/${account.id}`} />
              ))}
            </div>
          )}
    </div>
  );
}
