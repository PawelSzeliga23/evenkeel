import { Outlet } from "react-router";
import { Nav } from "./Nav";
import styles from "./shell.module.css";

export function AppShell() {
  return (
    <div className={styles.shell}>
      <main className={styles.main}><Outlet /></main>
      <Nav />
    </div>
  );
}
