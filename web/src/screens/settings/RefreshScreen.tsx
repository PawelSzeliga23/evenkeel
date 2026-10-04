import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { RefreshSchedule } from "../../api/types";
import { formatRefreshed } from "../../format";
import { BackLink } from "../../ui/BackLink";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import styles from "./Settings.module.css";

/** „9:00” from the API's „09:00”. */
const hour = (hhmm: string) => hhmm.replace(/^0(\d)/, "$1");

/** The value of the Ustawienia row: „co 30 min”. */
export const everyLabel = (schedule: RefreshSchedule) => `co ${schedule.intraday_every_minutes} min`;

/** Ustawienia → Odświeżanie cen (plan 8c): the shared schedule of the worker, read only. */
export function RefreshScreen() {
  const schedule = useQuery({ queryKey: keys.refreshSchedule, queryFn: api.refreshSchedule });
  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <h1 className={ui.pageTitle}>Odświeżanie cen</h1>
      {schedule.isPending ? <Skeleton rows={3} /> : schedule.isError
        ? <ErrorState error={schedule.error} onRetry={() => void schedule.refetch()} />
        : (
          <ul className={styles.facts}>
            <li>{`Co ${schedule.data.intraday_every_minutes} minut w dni robocze, ${hour(schedule.data.intraday_from)}–${hour(schedule.data.intraday_to)}.`}</li>
            <li>{`Pełna aktualizacja codziennie o ${hour(schedule.data.daily_at)}.`}</li>
            <li>{schedule.data.last_refreshed_at
              ? `Ostatnio: ${formatRefreshed(schedule.data.last_refreshed_at)}.` : "Ceny nie były jeszcze odświeżane."}</li>
            <li className="dim">Na Pulpicie możesz odświeżyć ceny od razu przyciskiem ⟳. Harmonogram jest wspólny dla całej aplikacji.</li>
          </ul>
        )}
    </div>
  );
}
