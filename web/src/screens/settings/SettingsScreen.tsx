import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { useSession } from "../../auth/session";
import { usePrivacy } from "../../settings/privacy";
import { usePreferences } from "../../settings/preferences";
import { useTheme } from "../../settings/theme";
import { GROUPS, SETTINGS, searchSettings } from "../../settings/registry";
import shell from "../../shell/shell.module.css";
import { BackLink } from "../../ui/BackLink";
import { ListRow } from "../../ui/ListRow";
import ui from "../../ui/ui.module.css";
import { START_SCREENS } from "./appearance";
import { problemCount } from "./model";
import { everyLabel } from "./RefreshScreen";
import styles from "./Settings.module.css";

const CHEVRON = <span className={styles.chevron} aria-hidden="true">›</span>;

/** Ustawienia (plan 8a): a search field over grouped rows, each opening its subpage. */
export function SettingsScreen() {
  const { state } = useSession();
  const notice = (useLocation().state as { notice?: string } | null)?.notice;
  const [query, setQuery] = useState("");
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const instruments = useQuery({ queryKey: keys.instruments, queryFn: api.instruments });
  const tags = useQuery({ queryKey: keys.tags, queryFn: api.tags });
  const schedule = useQuery({ queryKey: keys.refreshSchedule, queryFn: api.refreshSchedule });
  const [hidden] = usePrivacy();
  const [theme] = useTheme();
  const prefs = usePreferences();
  const problems = instruments.data ? problemCount(instruments.data) : null;
  const values: Record<string, string | undefined> = {
    profile: state.status === "signedIn" ? state.user.email : undefined,
    accounts: accounts.data ? String(accounts.data.length) : undefined,
    sources: problems === null ? undefined : problems ? `${problems} do sprawdzenia` : "w porządku",
    tags: tags.data ? String(tags.data.length) : undefined,
    theme: theme === "light" ? "jasny" : "ciemny",
    hide: hidden ? "wł." : "wył.",
    start: START_SCREENS.find((s) => s.value === prefs.start_screen)?.label,
    refresh: schedule.data ? everyLabel(schedule.data) : undefined,
    about: __APP_VERSION__,
  };
  const hits = searchSettings(query, accounts.data ?? [], tags.data ?? []);

  return (
    <div className={ui.page}>
      <div className={shell.phoneOnly}><BackLink to="/" label="Pulpit" /></div>
      <h1 className={ui.pageTitle}>Ustawienia</h1>
      {notice && <p className={ui.notice} role="status">{notice}</p>}
      <input type="search" className={styles.search} placeholder="Szukaj w ustawieniach" aria-label="Szukaj w ustawieniach"
        value={query} onChange={(e) => setQuery(e.target.value)} />
      {query.trim() ? (
        hits.length === 0 ? <p className="dim">{`Brak wyników dla „${query.trim()}”.`}</p> : (
          <div className={styles.group}>
            {hits.map((hit) => (
              <ListRow key={`${hit.to}-${hit.title}`} lead={hit.title.slice(0, 1)} title={hit.title} value={CHEVRON}
                subtitle={hit.place} to={hit.to} />
            ))}
          </div>
        )
      ) : GROUPS.map((group) => (
        <section key={group} className={ui.section} aria-label={group}>
          <h2 className={ui.sectionTitle}>{group}</h2>
          <div className={styles.group}>
            {SETTINGS.filter((s) => s.group === group && !s.parent).map((s) => (
              <ListRow key={s.id} lead={s.title.slice(0, 1)} title={s.title} to={s.to}
                subtitle={s.id === "profile" ? values.profile : undefined}
                value={<>{s.id === "profile" ? "" : values[s.id] ?? ""}{CHEVRON}</>} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
