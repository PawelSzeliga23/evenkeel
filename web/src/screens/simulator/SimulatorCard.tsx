import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import ui from "../../ui/ui.module.css";
import styles from "./Simulator.module.css";
import { NEW_PATH, ScenarioRow, useScenarioResults } from "./SimulatorScreen";

const LATEST = 3;

/** The latest three scenarios on Analiza; nothing while the list cannot be read. */
export function SimulatorCard() {
  const scenarios = useQuery({ queryKey: keys.scenarios, queryFn: api.scenarios });
  const latest = (scenarios.data ?? []).slice(0, LATEST);
  const results = useScenarioResults(latest, "all");
  if (!scenarios.data) return null;
  return (
    <section className={ui.section} aria-labelledby="simulator-title">
      <div className={ui.sectionHead}>
        <h2 id="simulator-title" className={ui.sectionTitle}>Symulator</h2>
        <Link className={ui.sectionMore} to="/analiza/symulator">Wszystkie scenariusze</Link>
      </div>
      {latest.length === 0
        ? <p className={styles.hint}>Sprawdź, jak wyglądałby Twój portfel przy innych decyzjach.</p>
        : <div>{latest.map((scenario, index) => <ScenarioRow key={scenario.id} scenario={scenario} result={results[index]?.data} />)}</div>}
      <Link className={ui.secondary} to={NEW_PATH}>Nowy scenariusz</Link>
    </section>
  );
}
