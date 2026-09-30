import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/client";
import { errorMessage } from "../api/messages";
import { Logo } from "../brand/Logo";
import styles from "./AuthScreens.module.css";
import { useSession } from "./session";

const MIN_PASSWORD = 10;
const PASSWORD_TOO_SHORT = `Hasło musi mieć co najmniej ${MIN_PASSWORD} znaków.`;

function registrationError(error: unknown): string {
  if (error instanceof ApiError && error.code === "validation_error") {
    const fields = ((error.details.errors as { loc: string[] }[] | undefined) ?? []).flatMap((e) => e.loc);
    if (fields.includes("password")) return PASSWORD_TOO_SHORT;
    if (fields.includes("email")) return "Podaj poprawny adres e-mail.";
  }
  return errorMessage(error);
}

export function RegisterScreen() {
  const { register } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [needsInvite, setNeedsInvite] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (password.length < MIN_PASSWORD) {
      setError(PASSWORD_TOO_SHORT);
      return;
    }
    setBusy(true);
    try {
      await register({ email: email.trim(), password, ...(needsInvite ? { invite_code: inviteCode.trim() } : {}) });
    } catch (err) {
      if (err instanceof ApiError && err.code === "invite_required") setNeedsInvite(true);
      setError(registrationError(err));
      setBusy(false);
    }
  }

  return (
    <main className={styles.screen}>
      <form className={styles.form} onSubmit={submit} noValidate>
        <div className={styles.brand}><Logo layout="stacked" /></div>
        <h1 className={styles.title}>Załóż konto</h1>
        <p className={styles.lead}>Twoje dane widzisz tylko ty.</p>
        <div className={styles.field}>
          <label htmlFor="register-email">E-mail</label>
          <input id="register-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className={styles.field}>
          <label htmlFor="register-password">Hasło</label>
          <input id="register-password" type="password" autoComplete="new-password" value={password}
            onChange={(e) => setPassword(e.target.value)} aria-describedby="register-password-hint" required />
          <small id="register-password-hint" className={styles.hint}>Co najmniej {MIN_PASSWORD} znaków.</small>
        </div>
        {needsInvite && (
          <div className={styles.field}>
            <label htmlFor="register-invite">Kod zaproszenia</label>
            <input id="register-invite" autoComplete="off" value={inviteCode} onChange={(e) => setInviteCode(e.target.value)} />
          </div>
        )}
        {error && <p className={styles.error} role="alert">{error}</p>}
        <button className={styles.primary} type="submit" disabled={busy}>Załóż konto</button>
        <p className={styles.switch}>Masz już konto? <Link to="/logowanie">Zaloguj się</Link></p>
      </form>
    </main>
  );
}
