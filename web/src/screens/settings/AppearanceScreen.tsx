import { BackLink } from "../../ui/BackLink";
import { Field } from "../../ui/forms";
import ui from "../../ui/ui.module.css";
import type { StartScreen } from "../../api/types";
import { usePreferences, useSavePreferences } from "../../settings/preferences";
import { usePrivacy } from "../../settings/privacy";
import { useHashScroll } from "../../settings/useHashScroll";
import { START_SCREENS } from "./appearance";

export function AppearanceScreen() {
  const [hidden, setHidden] = usePrivacy();
  const prefs = usePreferences();
  const save = useSavePreferences();
  useHashScroll();
  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <h1 className={ui.pageTitle}>Wygląd i prywatność</h1>
      <section className={ui.section} aria-label="Ukrywanie kwot">
        <label className={ui.toggle}>
          <input type="checkbox" role="switch" checked={hidden} aria-describedby="hide-hint"
            onChange={(e) => setHidden(e.target.checked)} />
          <span>Ukrywaj kwoty</span>
        </label>
        <small id="hide-hint" className="dim">Kwoty jako ••••; procenty i wykresy zostają. Tylko na tym urządzeniu.</small>
      </section>
      <section id="start" className={ui.section}>
        <Field id="start-screen" label="Ekran startowy" hint="Otwiera się po zalogowaniu i przy uruchomieniu aplikacji.">
          <select id="start-screen" value={prefs.start_screen}
            onChange={(e) => save.mutate({ start_screen: e.target.value as StartScreen })}>
            {START_SCREENS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Field>
      </section>
      {save.isSuccess && <p className={ui.notice} role="status">Zapisano.</p>}
    </div>
  );
}
