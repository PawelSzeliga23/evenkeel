import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { formatPercent, signOf } from "../../format";
import { HELP } from "../../ui/help";
import { InfoTip } from "../../ui/InfoTip";
import ui from "../../ui/ui.module.css";
import { shownReturn } from "./model";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

/** XIRR and the max drawdown of the whole history; hidden until there is a valuation (or when the request fails). */
export function AnalyticsCard() {
  const [accountIds, , ready] = useAccountSelection();
  const analytics = useQuery({
    queryKey: keys.analytics(accountIds, "all"), queryFn: () => api.analytics(accountIds, "all"), enabled: ready,
  });
  const data = analytics.data;
  if (!data || data.period === null) return null;
  const xirr = shownReturn(data.xirr, data.period.annualized).value;
  const xirrSpan = data.period.annualized ? "rocznie" : "za okres";
  const fall = data.max_drawdown?.pct ?? null;
  return (
    <section className={ui.section} aria-labelledby="analytics-title">
      <div className={ui.sectionHead}>
        <h2 id="analytics-title" className={ui.sectionTitle}>Analiza</h2>
        <Link className={ui.sectionMore} to="/analiza" aria-label="Szczegóły analizy">Szczegóły</Link>
      </div>
      <dl className={ui.kv}>
        <dt><span>XIRR</span> <small className="dim">{xirrSpan}</small><InfoTip label="XIRR" help={HELP.XIRR!} /></dt>
        <dd className={tone(xirr)}>{formatPercent(xirr, { places: 1 })}</dd>
        <dt><span>Maks. obsunięcie</span><InfoTip label="Maks. obsunięcie" help={HELP["Maks. obsunięcie"]!} /></dt>
        <dd className={tone(fall)}>{formatPercent(fall, { places: 1 })}</dd>
      </dl>
    </section>
  );
}
