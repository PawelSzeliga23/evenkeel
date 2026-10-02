import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { useSession } from "../../auth/session";
import { Logo } from "../../brand/Logo";
import shell from "../../shell/shell.module.css";
import { BackLink } from "../../ui/BackLink";
import { ListRow } from "../../ui/ListRow";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { ACCOUNT_KIND, WRAPPER, problemsSummary } from "./model";
import styles from "./Settings.module.css";

export function SettingsScreen() {
  const { state, signOut } = useSession();
  const notice = (useLocation().state as { notice?: string } | null)?.notice;
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const instruments = useQuery({ queryKey: keys.instruments, queryFn: api.instruments });

  return (
    <div className={ui.page}>
      <div className={shell.phoneOnly}><BackLink to="/" label="Pulpit" /></div>
      <h1 className={ui.pageTitle}>Ustawienia</h1>
      {notice && <p className={ui.notice} role="status">{notice}</p>}

      <section className={ui.section} aria-labelledby="profile-title">
        <h2 id="profile-title" className={ui.sectionTitle}>Profil</h2>
        <p>{state.status === "signedIn" ? state.user.email : ""}</p>
        <div className={styles.actions}>
          <Link className={ui.secondary} to="/ustawienia/haslo">Zmień hasło</Link>
          <button type="button" className={ui.secondary} onClick={() => { signOut().catch(() => {}); }}>Wyloguj</button>
        </div>
      </section>

      <section className={ui.section} aria-labelledby="accounts-title">
        <h2 id="accounts-title" className={ui.sectionTitle}>Konta</h2>
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
      </section>

      <section className={ui.section} aria-labelledby="sources-title">
        <h2 id="sources-title" className={ui.sectionTitle}>Źródła cen</h2>
        {instruments.isPending ? <Skeleton rows={1} />
          : instruments.isError ? <ErrorState error={instruments.error} onRetry={() => void instruments.refetch()} />
          : <p>{problemsSummary(instruments.data)}</p>}
        <Link className={`${ui.secondary} ${styles.start}`} to="/ustawienia/zrodla-cen">Zobacz źródła cen</Link>
      </section>

      <section className={ui.section} aria-labelledby="tags-title">
        <h2 id="tags-title" className={ui.sectionTitle}>Tagi walorów</h2>
        <p className="dim">Nazwy i kolory tagów. Tagi dodajesz w szczegółach pozycji.</p>
        <Link className={`${ui.secondary} ${styles.start}`} to="/ustawienia/tagi">Tagi</Link>
      </section>

      <section className={styles.about} aria-label="O aplikacji">
        <Logo layout="inline" />
        <small className="dim">Wersja {__APP_VERSION__}</small>
      </section>
    </div>
  );
}
