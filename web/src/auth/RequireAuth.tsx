import { Navigate, Outlet, useLocation } from "react-router";
import styles from "./AuthScreens.module.css";
import { useSession } from "./session";

export function Splash() {
  return <div className={styles.splash} aria-busy="true" aria-label="Wczytuję" />;
}

export function RequireAuth() {
  const { state } = useSession();
  const location = useLocation();
  if (state.status === "loading") return <Splash />;
  if (state.status === "anonymous") {
    return <Navigate to="/logowanie" replace state={{ from: location.pathname, expired: state.expired }} />;
  }
  return <Outlet />;
}

export function GuestOnly() {
  const { state } = useSession();
  const location = useLocation();
  if (state.status === "loading") return <Splash />;
  if (state.status === "signedIn") {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from && from !== "/logowanie" ? from : "/"} replace />;
  }
  return <Outlet />;
}
