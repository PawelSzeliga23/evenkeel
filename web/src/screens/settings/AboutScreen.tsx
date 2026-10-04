import { Logo } from "../../brand/Logo";
import { BackLink } from "../../ui/BackLink";
import ui from "../../ui/ui.module.css";
import styles from "./Settings.module.css";

/** Ustawienia → O aplikacji. */
export function AboutScreen() {
  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <h1 className={ui.pageTitle}>O aplikacji</h1>
      <section className={styles.about} aria-label="O aplikacji">
        <Logo layout="inline" />
        <small className="dim">Wersja {__APP_VERSION__}</small>
      </section>
    </div>
  );
}
