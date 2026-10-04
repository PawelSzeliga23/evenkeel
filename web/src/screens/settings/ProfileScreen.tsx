import { Link } from "react-router";
import { useSession } from "../../auth/session";
import { useHashScroll } from "../../settings/useHashScroll";
import { BackLink } from "../../ui/BackLink";
import ui from "../../ui/ui.module.css";
import styles from "./Settings.module.css";

/** Ustawienia → Profil: the e-mail, the password, the sessions, signing out and deleting the account. */
export function ProfileScreen() {
  const { state, signOut } = useSession();
  useHashScroll();
  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <h1 className={ui.pageTitle}>Profil</h1>
      <section className={ui.section} aria-label="Profil">
        <p>{state.status === "signedIn" ? state.user.email : ""}</p>
        <div className={styles.actions}>
          <Link className={ui.secondary} to="/ustawienia/haslo">Zmień hasło</Link>
          <Link className={ui.secondary} to="/ustawienia/sesje">Sesje i urządzenia</Link>
          <button id="wyloguj" type="button" className={ui.secondary} onClick={() => { signOut().catch(() => {}); }}>
            Wyloguj
          </button>
        </div>
      </section>
      <section className={ui.section} aria-label="Usuwanie konta">
        <Link className={styles.dangerLink} to="/ustawienia/usun-konto">Usuń konto</Link>
      </section>
    </div>
  );
}
