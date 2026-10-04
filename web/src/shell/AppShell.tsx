import { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";
import { START_SCREENS } from "../screens/settings/appearance";
import { usePreferences } from "../settings/preferences";
import { PrivacyProvider, takeRefocus, usePrivacy } from "../settings/privacy";
import { Nav } from "./Nav";
import styles from "./shell.module.css";

const STARTED = "evenkeel.started";

/** Opens the chosen start screen once per tab session, when the app is entered at „/”. */
function useStartScreen() {
  const { start_screen } = usePreferences();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    let started = true;
    try { started = sessionStorage.getItem(STARTED) === "1"; sessionStorage.setItem(STARTED, "1"); } catch { /* none */ }
    const path = START_SCREENS.find((s) => s.value === start_screen)?.path ?? "/";
    if (!started && pathname === "/" && path !== "/") navigate(path, { replace: true });
    // once, on entering the app
  }, []);
}

function Shell() {
  const [hidden] = usePrivacy();
  const wide = useLocation().pathname === "/"; // the Pulpit's tiles use the width of a computer (plan 9)
  useStartScreen();
  useEffect(() => {
    const id = takeRefocus();
    if (id) document.getElementById(id)?.focus();
  }, [hidden]);
  return (
    <div className={styles.shell}>
      {/* a new key re-renders the screen with the amounts shown or hidden */}
      <main key={String(hidden)} className={styles.main} data-wide={wide || undefined}><Outlet /></main>
      <Nav />
    </div>
  );
}

export function AppShell() {
  return <PrivacyProvider><Shell /></PrivacyProvider>;
}
