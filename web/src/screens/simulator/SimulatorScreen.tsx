import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { AnalyticsPeriod, Scenario, ScenarioResult } from "../../api/types";
import { ComparisonChart, swatchStyle } from "../../charts/ComparisonChart";
import { AccountSelect } from "../../ui/AccountPicker";
import { BackLink } from "../../ui/BackLink";
import { ListRow } from "../../ui/ListRow";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import analysis from "../analysis/Analysis.module.css";
import { PERIODS } from "../analysis/model";
import { RECALC_POLL_MS } from "../dashboard/model";
import { chartData, type ShownResult } from "./chart";
import { Measures, type Column } from "./Measures";
import { BASES, MAX_LINES, PORTFOLIO_COLOR, SLOTS, defaultShown, difference, toggleShown, type Shown } from "./model";
import styles from "./Simulator.module.css";

export const NEW_PATH = "/analiza/symulator/nowy";
const baseLabel = (scenario: Scenario) => BASES.find((base) => base.value === scenario.base)!.label;

/** Each scenario's result for the chosen accounts and period, in the order of `scenarios`. */
export function useScenarioResults(scenarios: Scenario[], period: AnalyticsPeriod) {
  const [accountIds, , ready] = useAccountSelection();
  return useQueries({
    queries: scenarios.map((scenario) => ({
      queryKey: keys.scenarioResult(scenario.id, accountIds, period),
      queryFn: () => api.scenarioResult(scenario.id, accountIds, period),
      enabled: ready,
      placeholderData: (previous: ScenarioResult | undefined) => previous,
      refetchInterval: (query: { state: { data?: ScenarioResult } }) =>
        (query.state.data?.recalculating ? RECALC_POLL_MS : false),
    })),
  });
}

function LeadIcon() {
  return (
    <svg className={styles.lead} viewBox="0 0 18 18" aria-hidden="true">
      <path d="M2 14 7 8l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** A row per scenario: its name, starting point and difference against the portfolio. */
export function ScenarioRow({ scenario, result }: { scenario: Scenario; result: ScenarioResult | undefined }) {
  const text = result ? difference(result) ?? "brak wyceny" : "liczę…";
  return (
    <ListRow to={`/analiza/symulator/${scenario.id}`} lead={<LeadIcon />} title={scenario.name}
      subtitle={baseLabel(scenario)} value={<small className="dim">{text}</small>} />
  );
}

export function SimulatorScreen() {
  const [accountIds, setAccountIds] = useAccountSelection();
  const [period, setPeriod] = useState<AnalyticsPeriod>("all");
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const scenarios = useQuery({ queryKey: keys.scenarios, queryFn: api.scenarios });
  const list = scenarios.data ?? [];
  const [picked, setPicked] = useState<Shown[] | null>(null);
  const [showPortfolio, setShowPortfolio] = useState(true);
  const known = new Set(list.map((scenario) => scenario.id));
  const shown = (picked ?? defaultShown(list.map((scenario) => scenario.id))).filter((item) => known.has(item.id));
  // Only the shown scenarios are simulated for the chosen period (the first one stands in for the real line when
  // none is shown); the list's differences are for the whole history, shared with the Analiza card.
  const charted = shown.length > 0
    ? shown.map((item) => list.find((scenario) => scenario.id === item.id)!) : list.slice(0, 1);
  const chartedResults = useScenarioResults(charted, period);
  const listResults = useScenarioResults(list, "all");
  const resultOf = (id: number) => chartedResults[charted.findIndex((scenario) => scenario.id === id)]?.data;

  const visible: ShownResult[] = shown.flatMap(({ id, slot }) => {
    const result = resultOf(id);
    const scenario = list.find((item) => item.id === id)!;
    return result ? [{ key: String(id), label: scenario.name, slot, result }] : [];
  });
  const base = visible[0]?.result ?? chartedResults.find((query) => query.data)?.data;
  const data = chartData(visible, showPortfolio, base);
  const results = [...chartedResults, ...listResults];
  const columns: Column[] = [
    { key: "portfolio", label: "Mój portfel", color: PORTFOLIO_COLOR, measures: base?.portfolio ?? null },
    ...visible.map(({ key, label, slot, result }) => ({ key, label, ...SLOTS[slot]!, measures: result.scenario })),
  ];

  return (
    <div className={ui.page}>
      <BackLink to="/analiza" label="Analiza" />
      <div className={styles.head}>
        <h1 className={ui.pageTitle}>Symulator</h1>
        <Link className={ui.primaryButton} to={NEW_PATH}>Nowy scenariusz</Link>
      </div>
      {accounts.data && <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />}
      <Segmented label="Okres" options={PERIODS} value={period} onChange={setPeriod} className={analysis.periods} />
      {scenarios.isPending ? <Skeleton rows={4} chart />
        : scenarios.isError ? <ErrorState error={scenarios.error} onRetry={() => void scenarios.refetch()} />
        : list.length === 0 ? (
          <EmptyState title="Nie masz jeszcze scenariuszy."
            action={<Link className={ui.primaryButton} to={NEW_PATH}>Nowy scenariusz</Link>} />
        ) : (
          <>
            {results.some((query) => query.data?.recalculating) && <Recalculating />}
            <section className={ui.section} aria-label="Porównanie">
              <div className={styles.legend} role="group" aria-label="Linie na wykresie">
                <button type="button" aria-pressed={showPortfolio} onClick={() => setShowPortfolio((was) => !was)}>
                  <i className={styles.swatch} style={swatchStyle(PORTFOLIO_COLOR)} /><span>Mój portfel</span>
                </button>
                {list.map((scenario) => {
                  const item = shown.find((entry) => entry.id === scenario.id);
                  const slot = item ? SLOTS[item.slot]! : null;
                  const full = !item && shown.length >= MAX_LINES; // focusable, and the hint says why it does nothing
                  return (
                    <button key={scenario.id} type="button" aria-pressed={Boolean(item)}
                      aria-disabled={full || undefined} aria-describedby={full ? "lines-hint" : undefined}
                      onClick={() => { if (!full) setPicked(toggleShown(shown, scenario.id)); }}>
                      <i className={styles.swatch} style={slot ? swatchStyle(slot.color, slot.dashed) : swatchStyle("var(--rule)")} />
                      <span>{scenario.name}</span>
                    </button>
                  );
                })}
              </div>
              {shown.length >= MAX_LINES && list.length > MAX_LINES && (
                <p id="lines-hint" className={styles.hint}>Na wykresie mieszczą się {MAX_LINES} scenariusze naraz — ukryj jeden, żeby pokazać inny.</p>
              )}
              {!base ? <Skeleton rows={0} chart />
                : data.lines.length === 0 ? <p className={styles.hint}>Wybierz linię na wykresie.</p>
                : <ComparisonChart {...data} />}
            </section>
            <section className={ui.section} aria-labelledby="measures-title">
              <h2 id="measures-title" className={ui.sectionTitle}>Miary</h2>
              <Measures columns={columns} />
            </section>
            <section className={ui.section} aria-labelledby="scenarios-title">
              <h2 id="scenarios-title" className={ui.sectionTitle}>Twoje scenariusze</h2>
              <div>
                {list.map((scenario, index) => <ScenarioRow key={scenario.id} scenario={scenario} result={listResults[index]?.data} />)}
              </div>
            </section>
          </>
        )}
    </div>
  );
}
