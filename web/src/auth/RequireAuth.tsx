import { Navigate, Outlet, useLocation } from "react-router";
import { AccountSelectionProvider } from "../accounts/AccountSelection";
import { ApiError, NETWORK_MESSAGE } from "../api/client";
import { usePreferences } from "../settings/preferences";
import { ErrorState } from "../ui/States";
import styles from "./AuthScreens.module.css";
import { useSession } from "./session";

export const SERVER_PROBLEM = "Serwer ma problem. Spróbuj ponownie za chwilę.";

export function Splash() {
  return <div className={styles.splash} aria-busy="true" aria-label="Wczytuję" />;
}

function Offline() {
  const { retry } = useSession();
  return (
    <div className={styles.offline}>
      <ErrorState error={new ApiError(0, "network", NETWORK_MESSAGE)} onRetry={retry} />
    </div>
  );
}

function ServerProblem() {
  const { retry } = useSession();
  return (
    <div className={styles.offline}>
      <ErrorState error={new ApiError(500, "server_error", SERVER_PROBLEM)} onRetry={retry} />
    </div>
  );
}

export function RequireAuth() {
  const { state } = useSession();
  const location = useLocation();
  const prefs = usePreferences();
  if (state.status === "loading") return <Splash />;
  if (state.status === "offline") return <Offline />;
  if (state.status === "serverError") return <ServerProblem />;
  if (state.status === "anonymous") {
    return <Navigate to="/logowanie" replace state={state.deleted ? { deleted: true }
      : { from: location.pathname, expired: state.expired, offlineLogout: state.offlineLogout === true }} />;
  }
  return (
    <AccountSelectionProvider key={state.user.id} userId={state.user.id} start={prefs.accounts_start}
      fixed={prefs.accounts_fixed}>
      <Outlet />
    </AccountSelectionProvider>
  );
}

export function GuestOnly() {
  const { state } = useSession();
  const location = useLocation();
  if (state.status === "loading") return <Splash />;
  if (state.status === "offline") return <Offline />;
  if (state.status === "serverError") return <ServerProblem />;
  if (state.status === "signedIn") {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from && from !== "/logowanie" ? from : "/"} replace />;
  }
  return <Outlet />;
}
