import { useId } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { signOf } from "../../format";
import { Money } from "../../ui/Amount";
import ui from "../../ui/ui.module.css";
import { RECALC_POLL_MS } from "../dashboard/model";

export const INCOME_PATH = "/analiza/dochod";

/** Income and costs of the year so far on Analiza; hidden until there is data (or when the request fails). */
export function IncomeCard() {
  const titleId = useId(); // a tile of the Pulpit can show the card twice (plan 9)
  const [accountIds, , ready] = useAccountSelection();
  const report = useQuery({
    queryKey: keys.income(accountIds, "ytd"), queryFn: () => api.income(accountIds, "ytd"), enabled: ready,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
  });
  const data = report.data;
  if (!data || data.period === null) return null;
  const costs = data.totals.costs_pln;
  return (
    <section className={ui.section} aria-labelledby={titleId}>
      <div className={ui.sectionHead}>
        <h2 id={titleId} className={ui.sectionTitle}>Dochód i koszty</h2>
        <Link className={ui.sectionMore} to={INCOME_PATH} aria-label="Szczegóły dochodu i kosztów">Szczegóły</Link>
      </div>
      <dl className={ui.kv}>
        <dt>Dochód od pocz. roku</dt>
        <dd><Money value={data.totals.income_pln} sign tone /></dd>
        <dt>Koszty od pocz. roku</dt>
        <dd><Money value={signOf(costs) > 0 ? `-${costs}` : costs} sign tone /></dd>
      </dl>
    </section>
  );
}
