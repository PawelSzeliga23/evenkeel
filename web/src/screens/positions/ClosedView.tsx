import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Closed, ClosedInvestment } from "../../api/types";
import { formatDate, formatDays, formatDecimal, formatPercent, signOf } from "../../format";
import { Money } from "../../ui/Amount";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { STATUS_LABEL, investmentKey, salesOf } from "./closedModel";
import styles from "./Positions.module.css";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

function Investment({ closed, investment }: { closed: Closed; investment: ClosedInvestment }) {
  const [open, setOpen] = useState(false);
  const label = `${investment.name}, ${investment.account_name}`;
  return (
    <li className={styles.closedItem}>
      <button type="button" className={styles.closedHead} aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className={styles.entryName}>
          <b>{investment.name}</b>
          <small>{`${investment.ticker} · ${investment.account_name}, ${STATUS_LABEL[investment.status]}, ${formatDate(investment.first_buy)} – ${formatDate(investment.last_sale)}`}</small>
        </span>
        <span className={styles.entryAmount}>
          <Money value={investment.total_pln} sign tone />
          <small className={`num ${tone(investment.return_pct)}`}>{formatPercent(investment.return_pct)}</small>
        </span>
      </button>
      {open && (
        <ul className={styles.list} aria-label={`Sprzedaże ${label}`}>
          {salesOf(closed, investment).map((sale, i) => (
            <li key={`${sale.closed_on}-${sale.quantity}-${sale.proceeds_pln}-${i}`} className={styles.entry}>
              <span className={styles.entryName}>
                <b>{formatDate(sale.closed_on)}</b>
                <small>{`${formatDecimal(sale.quantity, 8)} szt., ${formatDays(sale.holding_days)}`}</small>
              </span>
              <span className={styles.entryAmount}>
                <Money value={sale.realized_pln} sign tone />
                <small><Money value={sale.proceeds_pln} /></small>
              </span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function ClosedView({ accountIds, ready }: { accountIds: readonly number[]; ready: boolean }) {
  const closed = useQuery({ queryKey: keys.closed(accountIds), queryFn: () => api.closed(accountIds), enabled: ready, placeholderData: (previous) => previous });
  if (closed.isPending) return <Skeleton rows={4} />;
  if (closed.isError) return <ErrorState error={closed.error} onRetry={() => void closed.refetch()} />;
  const { totals, investments } = closed.data;
  if (investments.length === 0) return <EmptyState title="Nie masz jeszcze zamkniętych inwestycji." />;
  return (
    <>
      <section className={ui.section} aria-label="Wynik zamkniętych">
        <dl className={ui.kv}>
          <dt>Zysk ze sprzedaży</dt><dd><Money value={totals.realized_pln} sign tone /></dd>
          <dt>Dywidendy</dt><dd><Money value={totals.dividends_net_pln} sign tone /></dd>
          <dt>Koszty</dt><dd><Money value={totals.fees_pln} sign tone /></dd>
          <dt>Razem</dt><dd><Money value={totals.total_pln} sign tone /></dd>
          <dt>Zwrot</dt><dd className={`num ${tone(totals.return_pct)}`}>{formatPercent(totals.return_pct, { places: 1 })}</dd>
        </dl>
      </section>
      <ul className={styles.list}>
        {investments.map((investment) => <Investment key={investmentKey(investment)} closed={closed.data} investment={investment} />)}
      </ul>
    </>
  );
}
