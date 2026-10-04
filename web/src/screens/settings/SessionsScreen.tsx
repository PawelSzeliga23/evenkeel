import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { errorMessage } from "../../api/messages";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { describeDevice } from "../../auth/device";
import { formatDate, formatRefreshed, todayIso } from "../../format";
import { BackLink } from "../../ui/BackLink";
import { FormError } from "../../ui/forms";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import styles from "./Settings.module.css";

/** Ustawienia → Profil → Sesje i urządzenia (plan 8d): where the account is signed in, and signing devices out. */
export function SessionsScreen() {
  const queryClient = useQueryClient();
  const sessions = useQuery({ queryKey: keys.sessions, queryFn: api.sessions });
  const done = () => queryClient.invalidateQueries({ queryKey: keys.sessions });
  const revoke = useMutation({ mutationFn: api.revokeSession, onSuccess: done });
  const revokeOthers = useMutation({ mutationFn: api.revokeOtherSessions, onSuccess: done });
  const failed = revoke.error ?? revokeOthers.error;

  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia/profil" label="Profil" />
      <h1 className={ui.pageTitle}>Sesje i urządzenia</h1>
      {sessions.isPending ? <Skeleton rows={2} /> : sessions.isError
        ? <ErrorState error={sessions.error} onRetry={() => void sessions.refetch()} />
        : (
          <>
            <ul className={styles.sessions} aria-label="Sesje">
              {sessions.data.map((session) => (
                <li key={session.id}>
                  <span>
                    <b>{describeDevice(session.user_agent)}</b>
                    {session.current && <span className={styles.badge}>To urządzenie</span>}
                    <small className="dim">
                      {`Zalogowano ${formatDate(todayIso(new Date(session.started_at)))} · ostatnio ${formatRefreshed(session.last_used_at)}`}
                    </small>
                  </span>
                  {!session.current && (
                    <button type="button" className={ui.secondary} disabled={revoke.isPending}
                      aria-label={`Wyloguj ${describeDevice(session.user_agent)}`} onClick={() => revoke.mutate(session.id)}>
                      Wyloguj
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {sessions.data.some((s) => !s.current) && (
              <button type="button" className={ui.secondary} disabled={revokeOthers.isPending}
                onClick={() => revokeOthers.mutate()}>
                Wyloguj wszystkie inne
              </button>
            )}
            <FormError message={failed ? errorMessage(failed) : null} />
            <small className="dim">Wylogowane urządzenie traci dostęp najpóźniej po 15 minutach.</small>
          </>
        )}
    </div>
  );
}
