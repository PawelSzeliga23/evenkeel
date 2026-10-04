import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { AccountsStart, Preferences } from "../../api/types";
import { usePreferences, useSavePreferences } from "../../settings/preferences";
import { useHashScroll } from "../../settings/useHashScroll";
import { BackLink } from "../../ui/BackLink";
import { Field } from "../../ui/forms";
import ui from "../../ui/ui.module.css";
import { PERIODS as ANALYSIS_PERIODS } from "../analysis/model";
import { RANGES } from "../dashboard/model";
import { PERIODS as HOLDINGS_PERIODS } from "../holdings/model";
import { PRICE_RANGES } from "../positions/priceModel";
import styles from "./Settings.module.css";

const ACCOUNTS_START: { value: AccountsStart; label: string }[] = [
  { value: "last", label: "Ostatnio wybrane" }, { value: "all", label: "Zawsze cały portfel" },
  { value: "fixed", label: "Wybrane konta" },
];

type Choice = { value: string; label: string };
type ChoiceKey = "accounts_start" | "analysis_period" | "holdings_period" | "value_range" | "price_range";

/** Ustawienia → Domyślne widoki (plan 8a): what the screens open with; a change on a screen lasts the visit. */
export function DefaultsScreen() {
  const prefs = usePreferences();
  const save = useSavePreferences();
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  useHashScroll();

  const choose = (anchor: string, key: ChoiceKey, label: string, options: Choice[]) => (
    <section id={anchor} className={ui.section}>
      <Field id={`default-${anchor}`} label={label}>
        <select id={`default-${anchor}`} value={prefs[key]}
          onChange={(e) => save.mutate({ [key]: e.target.value } as Partial<Preferences>)}>
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </Field>
    </section>
  );
  const toggleFixed = (id: number, on: boolean) => {
    const next = on ? [...prefs.accounts_fixed, id] : prefs.accounts_fixed.filter((v) => v !== id);
    save.mutate({ accounts_fixed: next });
  };

  return (
    <div className={ui.page}>
      <BackLink to="/ustawienia" label="Ustawienia" />
      <h1 className={ui.pageTitle}>Domyślne widoki</h1>
      <p className="dim">Z tymi ustawieniami otwierają się ekrany; zmiana na ekranie działa do końca wizyty.</p>
      {choose("konta", "accounts_start", "Konta na starcie", ACCOUNTS_START)}
      {prefs.accounts_start === "fixed" && accounts.data && (
        <fieldset className={styles.panel}>
          <legend className="dim">Konta na starcie</legend>
          {accounts.data.map((account) => (
            <label key={account.id} className={ui.toggle}>
              <input type="checkbox" checked={prefs.accounts_fixed.includes(account.id)}
                onChange={(e) => toggleFixed(account.id, e.target.checked)} />
              <span>{account.name}</span>
            </label>
          ))}
        </fieldset>
      )}
      {choose("analiza", "analysis_period", "Okres w Analizie i Symulatorze", ANALYSIS_PERIODS)}
      {choose("walory", "holdings_period", "Okres w Walorach i Tagach", HOLDINGS_PERIODS)}
      {choose("wykres-wartosci", "value_range", "Zakres wykresu wartości", RANGES)}
      {choose("wykres-ceny", "price_range", "Zakres wykresu ceny", PRICE_RANGES)}
      <section id="bez-oszczednosci" className={ui.section}>
        <label className={ui.toggle}>
          <input type="checkbox" role="switch" checked={prefs.holdings_without_fixed_income}
            onChange={(e) => save.mutate({ holdings_without_fixed_income: e.target.checked })} />
          <span>Walory bez oszczędności i obligacji</span>
        </label>
      </section>
      {save.isSuccess && <p className={ui.notice} role="status">Zapisano.</p>}
    </div>
  );
}
