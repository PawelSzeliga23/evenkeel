import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router";
import { errorMessage } from "../api/messages";
import { Logo } from "../brand/Logo";
import styles from "./AuthScreens.module.css";
import { useSession } from "./session";

export function LoginScreen() {
  const { signIn } = useSession();
  const location = useLocation();
  const expired = (location.state as { expired?: boolean } | null)?.expired === true;
  const offlineLogout = (location.state as { offlineLogout?: boolean } | null)?.offlineLogout === true;
  const deleted = (location.state as { deleted?: boolean } | null)?.deleted === true;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email.trim(), password); // GuestOnly then moves on to the page asked for
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <main className={styles.screen}>
      <form className={styles.form} onSubmit={submit} noValidate>
        <h1 className={styles.title}><Logo layout="stacked" /></h1>
        <p className={styles.lead}>Zaloguj się, żeby zobaczyć swój portfel.</p>
        {expired && <p className={styles.notice} role="status">Sesja wygasła, zaloguj się ponownie.</p>}
        {deleted && <p className={styles.notice} role="status">Konto zostało usunięte.</p>}
        {offlineLogout && (
          <p className={styles.notice} role="status">
            Wylogowano na tym urządzeniu. Serwer był niedostępny, więc sesja na serwerze wygaśnie sama.
          </p>
        )}
        <div className={styles.field}>
          <label htmlFor="login-email">E-mail</label>
          <input id="login-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className={styles.field}>
          <label htmlFor="login-password">Hasło</label>
          <input id="login-password" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && <p className={styles.error} role="alert">{error}</p>}
        <button className={styles.primary} type="submit" disabled={busy}>Zaloguj się</button>
        <p className={styles.switch}>Nie masz konta? <Link to="/rejestracja">Załóż konto</Link></p>
      </form>
    </main>
  );
}
