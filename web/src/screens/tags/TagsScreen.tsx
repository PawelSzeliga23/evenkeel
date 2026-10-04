import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { HoldingsPeriod, TagsReport } from "../../api/types";
import { ComparisonChart, swatchStyle } from "../../charts/ComparisonChart";
import { formatPercent, signOf } from "../../format";
import { AccountSelect, AccountsFailed } from "../../ui/AccountPicker";
import { HeroAmount, Money } from "../../ui/Amount";
import { BackLink } from "../../ui/BackLink";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { RECALC_POLL_MS } from "../dashboard/model";
import holdingsStyles from "../holdings/Holdings.module.css";
import { PERIODS } from "../holdings/model";
import { tagColor } from "../../tags/model";
import { NO_TAGS, NO_VALUE, UNTAGGED, UNTAGGED_COLOR, chartLines, holdingsLabel, legend } from "./model";
import styles from "./Tags.module.css";
import { usePreferences } from "../../settings/preferences";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");
const share = (value: string | null) => formatPercent(value, { sign: false });

function Row({ name, color, value, sharePct, meta }: {
  name: string; color: string; value: string; sharePct: string | null; meta: ReactNode;
}) {
  return (
    <li className={styles.row}>
      <span className={styles.rowHead}>
        <i className={styles.dot} style={{ background: color }} aria-hidden="true" />
        <b>{name}</b>
        <Money value={value} />
      </span>
      <span className={styles.rowMeta}>{meta}</span>
      <span className={styles.bar} aria-hidden="true">
        <i style={{ width: `${Math.min(Math.max(Number(sharePct ?? 0), 0), 100)}%`, background: color }} />
      </span>
    </li>
  );
}

function Gain({ pln, pct }: { pln: string; pct: string | null }) {
  return <span><Money value={pln} sign tone /> <span className={`num ${tone(pct)}`}>({formatPercent(pct)})</span></span>;
}

function Shares({ report }: { report: TagsReport }) {
  return (
    <section className={ui.section} aria-labelledby="tags-shares">
      <h2 id="tags-shares" className={ui.sectionTitle}>Udział w portfelu</h2>
      {report.tags.length === 0 && <p className={styles.note}>{NO_VALUE}</p>}
      <ul className={styles.list} aria-label="Udział w portfelu">
        {report.tags.map((tag) => (
          <Row key={tag.id} name={tag.name} color={tagColor(tag.color)} value={tag.value_pln} sharePct={tag.share_pct}
            meta={<><span>{`${share(tag.share_pct)} · ${holdingsLabel(tag.holdings)}`}</span><Gain pln={tag.gain_pln} pct={tag.gain_pct} /></>} />
        ))}
        {report.untagged && (
          <Row name="bez tagu" color={UNTAGGED_COLOR} value={report.untagged.value_pln} sharePct={report.untagged.share_pct}
            meta={<><span>{`${share(report.untagged.share_pct)} · ${holdingsLabel(report.untagged.holdings)}`}</span>
              <Gain pln={report.untagged.gain_pln} pct={report.untagged.gain_pct} /></>} />
        )}
        <Row name="Gotówka" color="var(--dim)" value={report.cash.value_pln} sharePct={report.cash.share_pct}
          meta={<span>{share(report.cash.share_pct)}</span>} />
      </ul>
      <p className={styles.note}>Walor z kilkoma tagami liczy się w każdym z nich, więc udziały nie sumują się do 100 %.</p>
    </section>
  );
}

function History({ report }: { report: TagsReport }) {
  const [hidden, setHidden] = useState<ReadonlySet<string>>(() => new Set([UNTAGGED]));
  const toggle = (key: string) => setHidden((was) => {
    const next = new Set(was);
    if (!next.delete(key)) next.add(key);
    return next;
  });
  const lines = chartLines(report, hidden);
  return (
    <section className={ui.section} aria-labelledby="tags-history">
      <h2 id="tags-history" className={ui.sectionTitle}>Udział w czasie</h2>
      <div className={styles.legend} role="group" aria-label="Linie na wykresie">
        {legend(report).map((entry) => (
          <button key={entry.key} type="button" aria-pressed={!hidden.has(entry.key)} onClick={() => toggle(entry.key)}>
            <i className={styles.swatch} style={swatchStyle(entry.color)} /><span>{entry.label}</span>
          </button>
        ))}
      </div>
      {lines.length === 0 ? <p className={styles.note}>Wybierz linię na wykresie.</p> : (
        <ComparisonChart dates={report.history.dates} lines={lines} unit="percent"
          format={(value) => formatPercent(value, { sign: false, places: 1 })} />
      )}
      <p className={styles.note}>Liczone z obecnymi tagami na całej historii.</p>
    </section>
  );
}

/** Analiza → Tagi (plan 7f-1): value, share and period gain per tag, and each tag's share over time. */
export function TagsScreen() {
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  const prefs = usePreferences();
  const [period, setPeriod] = useState<HoldingsPeriod>(prefs.holdings_period);
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const report = useQuery({
    queryKey: keys.tagAnalytics(accountIds, period),
    queryFn: () => api.tagAnalytics(accountIds, period),
    enabled: ready,
    placeholderData: (previous) => previous,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
  });
  const tags = useQuery({ queryKey: keys.tags, queryFn: api.tags });
  const data = report.data;
  const noTags = data?.tags.length === 0 && tags.data?.length === 0;

  return (
    <div className={ui.page}>
      <BackLink to="/analiza" label="Analiza" />
      <h1 className={ui.pageTitle}>Tagi</h1>
      {accounts.data ? <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />
        : accounts.isError ? <AccountsFailed onRetry={() => void accounts.refetch()} /> : null}
      <Segmented label="Okres" options={PERIODS} value={period} className={holdingsStyles.periods} onChange={setPeriod} />
      {report.isPending || (data?.tags.length === 0 && tags.isPending) ? <Skeleton rows={4} />
        : report.isError ? <ErrorState error={report.error} onRetry={() => void report.refetch()} />
        : data!.period === null ? <EmptyState title="Nie ma jeszcze wyceny do pokazania." />
        : noTags ? <EmptyState title={NO_TAGS} />
        : (
          <div className={report.isPlaceholderData ? `${styles.body} ${styles.stale}` : styles.body}
            aria-busy={report.isPlaceholderData}>
            {data!.recalculating && <Recalculating />}
            <section className={styles.total} aria-label="Wartość portfela">
              <span className="dim">Wartość portfela</span>
              <HeroAmount value={data!.total_pln} size="m" />
            </section>
            <Shares report={data!} />
            {data!.tags.length > 0 && <History report={data!} />}
          </div>
        )}
    </div>
  );
}
