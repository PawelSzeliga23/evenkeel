import { useId } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import ui from "../../ui/ui.module.css";
import { RECALC_POLL_MS } from "../dashboard/model";
import { HeatMap } from "./HeatMap";

export const HOLDINGS_PATH = "/analiza/walory";

/** A small day map on Analiza; hidden until there is a valuation (or when the request fails). */
export function HoldingsCard({ height = 140, labels = true }: { height?: number; labels?: boolean } = {}) {
  const titleId = useId(); // a tile of the Pulpit can show the card twice (plan 9)
  const [accountIds, , ready] = useAccountSelection();
  const navigate = useNavigate();
  const holdings = useQuery({
    queryKey: keys.holdings(accountIds, "1d"), queryFn: () => api.holdings(accountIds, "1d"), enabled: ready,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
  });
  const data = holdings.data;
  if (!data || data.period === null) return null;
  return (
    <section className={ui.section} aria-labelledby={titleId}>
      <div className={ui.sectionHead}>
        <h2 id={titleId} className={ui.sectionTitle}>Walory</h2>
        <Link className={ui.sectionMore} to={HOLDINGS_PATH}>Walory</Link>
      </div>
      <HeatMap items={data.items} period="1d" onSelect={() => navigate(HOLDINGS_PATH)} height={height} labels={labels} />
    </section>
  );
}
