import { NavLink } from "react-router";
import { Logo } from "../brand/Logo";
import { AddIcon, AnalysisIcon, DashboardIcon, HistoryIcon, SettingsIcon, PositionsIcon } from "./icons";
import styles from "./shell.module.css";

/** Phone: five tabs, Analiza in place of Ustawienia (reached by the gear on Pulpit); desktop sidebar: all six. */
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
      <NavLink to="/ustawienia" className={`${styles.item} ${styles.desktopOnly}`}><SettingsIcon />Ustawienia</NavLink>
    </nav>
  );
}
