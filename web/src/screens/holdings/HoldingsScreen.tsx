import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { GroupGain, HoldingsPeriod } from "../../api/types";
import { formatDate, formatMoney, formatPercent, signOf } from "../../format";
import { AccountSelect } from "../../ui/AccountPicker";
import { Money } from "../../ui/Amount";
import { BackLink } from "../../ui/BackLink";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { RECALC_POLL_MS } from "../dashboard/model";
import { HeatMap, holdingLabel } from "./HeatMap";
import styles from "./Holdings.module.css";
import { GAIN_LABEL, PERIODS, ranked, shown, type Ranking, type Shown } from "./model";
import { usePreferences } from "../../settings/preferences";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");
const RANKINGS: { value: Ranking; label: string }[] = [{ value: "pln", label: "zł" }, { value: "pct", label: "%" }];

function Details({ row, period }: { row: Shown; period: HoldingsPeriod }) {
  const { item } = row;
  const title = item.ticker ? `${item.ticker} — ${item.name}` : item.name;
  return (
    <section className={styles.details} aria-label={title}>
      <b>{title}</b>
      <div>
        {GAIN_LABEL[period]} <b className={tone(item.gain_pln)}>{formatMoney(item.gain_pln, { sign: true })}</b>{" "}
        ({formatPercent(item.gain_pct)}) · wartość {formatMoney(item.value_pln)}{row.share && ` · ${row.share}`}
      </div>
      {item.accounts.map((account) => (
        <div key={account.account_id} className="dim">{account.name}: {formatMoney(account.gain_pln, { sign: true })}</div>
      ))}
    </section>
  );
}

function GroupTable({ title, head, rows }: { title: string; head: string; rows: GroupGain[] }) {
  return (
    <section className={ui.section}>
      <h2 className={ui.sectionTitle}>{title}</h2>
      <table className={styles.table} aria-label={title}>
        <thead><tr><th>{head}</th><th>Wartość</th><th>Zysk</th><th>%</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td>{row.name}</td>
              <td className="num">{formatMoney(row.value_pln)}</td>
              <td><Money value={row.gain_pln} sign tone /></td>
              <td className={`num ${tone(row.gain_pct)}`}>{formatPercent(row.gain_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** Analiza → Walory: the heat map, the ranking and the gains by account and kind for a period. */
export function HoldingsScreen() {
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  const prefs = usePreferences();
  const [period, setPeriod] = useState<HoldingsPeriod>(prefs.holdings_period);
  const [withoutFixedIncome, setWithoutFixedIncome] = useState(prefs.holdings_without_fixed_income);
  const [order, setOrder] = useState<Ranking>("pln");
  const [selected, setSelected] = useState<string | null>(null);
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const holdings = useQuery({
    queryKey: keys.holdings(accountIds, period),
    queryFn: () => api.holdings(accountIds, period),
    enabled: ready,
    placeholderData: (previous) => previous,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
  });
  const data = holdings.data;
  const rows = data ? shown(data.items, withoutFixedIncome) : [];
  const picked = rows.find((row) => row.item.key === selected);

  return (
    <div className={ui.page}>
      <BackLink to="/analiza" label="Analiza" />
      <h1 className={ui.pageTitle}>Walory</h1>
      {accounts.data && <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />}
      <Segmented label="Okres" options={PERIODS} value={period} className={styles.periods}
        onChange={(value) => { setPeriod(value); setSelected(null); }} />
      <label className={styles.check}>
        <input type="checkbox" checked={withoutFixedIncome}
          onChange={(event) => { setWithoutFixedIncome(event.target.checked); setSelected(null); }} />
        Bez oszczędności i obligacji
      </label>
      {holdings.isPending ? <Skeleton rows={4} />
        : holdings.isError ? <ErrorState error={holdings.error} onRetry={() => void holdings.refetch()} />
        : data!.period === null ? <EmptyState title="Nie ma jeszcze wyceny do pokazania." />
        : (
          <div className={holdings.isPlaceholderData ? `${styles.body} ${styles.stale}` : styles.body}
            aria-busy={holdings.isPlaceholderData}>
            {data!.recalculating && <Recalculating />}
            <section className={ui.section} aria-labelledby="map-title">
              <div className={ui.sectionHead}>
                <h2 id="map-title" className={ui.sectionTitle}>Mapa</h2>
                <small className="dim">
                  {data!.period.start === data!.period.end ? formatDate(data!.period.end)
                    : `${formatDate(data!.period.start)} – ${formatDate(data!.period.end)}`}
                </small>
              </div>
              <HeatMap items={rows.map((row) => row.item)} period={period} selected={picked ? selected : null}
                onSelect={(key) => setSelected(key === selected ? null : key)} />
              {picked ? <Details row={picked} period={period} />
                : <p className={styles.hint}>Wielkość = udział, kolor = zysk %. Dotknij kafelka, żeby zobaczyć szczegóły.</p>}
            </section>
            <section className={ui.section} aria-labelledby="ranking-title">
              <div className={ui.sectionHead}>
                <h2 id="ranking-title" className={ui.sectionTitle}>Ranking</h2>
                <Segmented label="Kolejność rankingu" options={RANKINGS} value={order} onChange={setOrder} className={styles.order} />
              </div>
              <ul className={styles.ranking} aria-label="Ranking">
                {ranked(rows, order).map(({ item, share, contribution }) => (
                  <li key={item.key} className={ui.row}>
                    <span className={ui.rowName}>
                      <b>{holdingLabel(item)}{item.ticker && <span className="dim"> {item.name}</span>}</b>
                      <small>{[share, contribution].filter(Boolean).join(" · ")}</small>
                    </span>
                    <span className={ui.rowAmount}>
                      <Money value={item.gain_pln} sign tone />
                      <small className={tone(item.gain_pct)}>{formatPercent(item.gain_pct)}</small>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
            <GroupTable title="Zysk według kont" head="Konto" rows={data!.by_account} />
            <GroupTable title="Zysk według typów" head="Typ" rows={data!.by_kind} />
          </div>
        )}
    </div>
  );
}
