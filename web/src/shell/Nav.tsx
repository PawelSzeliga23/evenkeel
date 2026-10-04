import { Link, NavLink } from "react-router";
import { Logo } from "../brand/Logo";
import { AddIcon, AnalysisIcon, DashboardIcon, EditTilesIcon, HistoryIcon, SettingsIcon, PositionsIcon } from "./icons";
import styles from "./shell.module.css";

/** Phone: five tabs, Ustawienia behind the gear on Pulpit; desktop sidebar: the five tabs, Ustawienia pinned to the bottom. */
export function Nav() {
  return (
    <nav className={styles.nav} aria-label="Główna">
      <div className={styles.sidebarBrand}><Logo layout="inline" /></div>
      <NavLink to="/" end className={styles.item}><DashboardIcon />Pulpit</NavLink>
      <NavLink to="/pozycje" className={styles.item}><PositionsIcon />Pozycje</NavLink>
      <NavLink to="/dodaj" className={styles.item}>
        <span className={styles.plus}><AddIcon /></span>Dodaj
      </NavLink>
      <NavLink to="/historia" className={styles.item}><HistoryIcon />Historia</NavLink>
      <NavLink to="/analiza" className={styles.item}><AnalysisIcon />Analiza</NavLink>
      {/* plan 9: on a phone the same button sits at the top of Pulpit */}
      <Link to="/?edycja" className={`${styles.item} ${styles.desktopOnly} ${styles.pinned}`}><EditTilesIcon />Edytuj pulpit</Link>
      <NavLink to="/ustawienia" className={`${styles.item} ${styles.desktopOnly} ${styles.afterPinned}`}><SettingsIcon />Ustawienia</NavLink>
    </nav>
  );
}
