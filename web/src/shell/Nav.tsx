import { NavLink } from "react-router";
import { Logo } from "../brand/Logo";
import { AddIcon, DashboardIcon, HistoryIcon, SettingsIcon, PositionsIcon } from "./icons";
import styles from "./shell.module.css";

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
      <NavLink to="/ustawienia" className={styles.item}><SettingsIcon />Ustawienia</NavLink>
    </nav>
  );
}
