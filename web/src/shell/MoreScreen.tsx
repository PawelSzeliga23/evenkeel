import { useSession } from "../auth/session";
import ui from "../ui/ui.module.css";
import styles from "./shell.module.css";

const COMING = [
  "Historia operacji", "Obligacje i konta oszczędnościowe", "Zamknięte inwestycje", "Ekspozycja walutowa",
  "Limity IKE i IKZE", "Ustawienia kont i tickerów",
];

export function MoreScreen() {
  const { state, signOut } = useSession();
  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Więcej</h1>
      <section className={ui.section}>
        <p className="dim">Zalogowano jako</p>
        <p>{state.status === "signedIn" ? state.user.email : ""}</p>
        <button type="button" className={`${ui.secondary} ${styles.signOut}`} onClick={() => { signOut().catch(() => {}); }}>Wyloguj</button>
      </section>
      <section className={ui.section}>
        <h2 className={ui.sectionTitle}>Wkrótce</h2>
        <ul className={styles.coming}>
          {COMING.map((item) => <li key={item}><span>{item}</span><span className="dim">wkrótce</span></li>)}
        </ul>
      </section>
    </div>
  );
}
