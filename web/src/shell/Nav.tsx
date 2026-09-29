import { NavLink } from "react-router";
import { AddIcon, DashboardIcon, HistoryIcon, MoreIcon, PositionsIcon } from "./icons";
import styles from "./shell.module.css";

export function Nav() {
  return (
    <nav className={styles.nav} aria-label="Główna">
      <NavLink to="/" end className={styles.item}><DashboardIcon />Pulpit</NavLink>
      <NavLink to="/pozycje" className={styles.item}><PositionsIcon />Pozycje</NavLink>
      <NavLink to="/dodaj" className={styles.item}>
        <span className={styles.plus}><AddIcon /></span>Dodaj
      </NavLink>
      <NavLink to="/historia" className={styles.item}><HistoryIcon />Historia</NavLink>
      <NavLink to="/wiecej" className={styles.item}><MoreIcon />Więcej</NavLink>
    </nav>
  );
}
