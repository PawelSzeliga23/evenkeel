import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { ShareChart } from "../../charts/ShareChart";
import { colorOf, shareSeries, sharePoints } from "../../charts/shares";
import { formatPercent, todayIso } from "../../format";
import { AccountSelect, AccountsFailed } from "../../ui/AccountPicker";
import { Money } from "../../ui/Amount";
import { BackLink } from "../../ui/BackLink";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { rangeFrom, type Range } from "../dashboard/model";
import { usePreferences } from "../../settings/preferences";

const RANGES: { value: Range; label: string }[] = [
  { value: "3M", label: "3M" }, { value: "1R", label: "1R" }, { value: "ALL", label: "Wszystko" },
];

export function ExposureScreen() {
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  const prefs = usePreferences();
  const [range, setRange] = useState<Range>(prefs.value_range);
  const from = rangeFrom(range, todayIso());
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const exposure = useQuery({
    queryKey: keys.exposureHistory(accountIds, from), queryFn: () => api.exposureHistory(accountIds, from),
    enabled: ready,
    placeholderData: (previous) => previous,
  });
  const series = exposure.data ? shareSeries(exposure.data) : [];

  return (
    <div className={ui.page}>
      <BackLink to="/" label="Pulpit" />
      <div>
        <h1 className={ui.pageTitle}>Ekspozycja walutowa</h1>
        <p className="dim">Udział wartości portfela. Liczy się waluta notowania, nie waluta aktywów bazowych (np. ETF na S&P 500 notowany w EUR liczy się jako EUR).</p>
      </div>
      {accounts.data ? <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />
        : accounts.isError ? <AccountsFailed onRetry={() => void accounts.refetch()} /> : null}
      {exposure.isPending ? <Skeleton chart rows={2} />
        : exposure.isError ? <ErrorState error={exposure.error} onRetry={() => void exposure.refetch()} />
        : exposure.data.current.length === 0 ? <EmptyState title="Nie ma jeszcze wyceny do pokazania." />
        : (
          <>
            <section className={ui.section} aria-label="Dziś">
              <dl className={ui.kv}>
                {exposure.data.current.map((item) => (
                  <div key={item.currency} style={{ display: "contents" }}>
                    <dt>
                      <i style={{ display: "inline-block", width: 9, height: 9, borderRadius: 3, marginRight: 8, background: colorOf(series, item.currency) }} />
                      {item.currency === "unknown" ? "Nieznana" : item.currency}
                    </dt>
                    <dd><Money value={item.value_pln} /> <span className="dim">{formatPercent(item.share_pct, { sign: false, places: 1 })}</span></dd>
                  </div>
                ))}
              </dl>
            </section>
            <section className={ui.section} aria-label="W czasie">
              <ShareChart series={series} points={sharePoints(exposure.data, series)} />
              <Segmented label="Zakres wykresu" options={RANGES} value={range} onChange={setRange} />
            </section>
          </>
        )}
    </div>
  );
}
