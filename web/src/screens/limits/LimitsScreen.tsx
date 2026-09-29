import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { formatMoney } from "../../format";
import { Money } from "../../ui/Amount";
import { BackLink } from "../../ui/BackLink";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { LimitBar } from "./LimitsCard";
import styles from "./Limits.module.css";
import { WRAPPER_LABEL, byWrapper, overBy } from "./model";

export function LimitsScreen() {
  const limits = useQuery({ queryKey: keys.limits, queryFn: api.limits });
  return (
    <div className={ui.page}>
      <BackLink to="/" label="Pulpit" />
      <div>
        <h1 className={ui.pageTitle}>Limity IKE i IKZE</h1>
        <p className="dim">Wpłaty w roku kalendarzowym na wszystkie konta danego typu; wypłata nie zwalnia limitu.</p>
      </div>
      {limits.isPending ? <Skeleton rows={4} />
        : limits.isError ? <ErrorState error={limits.error} onRetry={() => void limits.refetch()} />
        : limits.data.length === 0 ? <EmptyState title="Nie masz konta IKE ani IKZE." />
        : byWrapper(limits.data).map(({ wrapper, current, earlier }) => {
          const over = overBy(current);
          return (
            <section key={wrapper} className={ui.section} aria-labelledby={`limit-${wrapper}`}>
              <h2 id={`limit-${wrapper}`} className={ui.sectionTitle}>{WRAPPER_LABEL[wrapper]}</h2>
              <p>
                {current.limit_pln === null
                  ? `Wpłacono ${formatMoney(current.paid_pln)} w ${current.year}, brak limitu w danych`
                  : `Wpłacono ${formatMoney(current.paid_pln)} z ${formatMoney(current.limit_pln)} w ${current.year}`}
              </p>
              <LimitBar limit={current} />
              {over !== null ? <p className="down">{`Przekroczono limit o ${formatMoney(over)}`}</p>
                : current.remaining_pln !== null && <p className="dim">{`Zostało ${formatMoney(current.remaining_pln)}`}</p>}
              <dl className={ui.kv}>
                {current.accounts.map((a) => <div key={a.account_id} style={{ display: "contents" }}><dt>{a.name}</dt><dd><Money value={a.paid_pln} /></dd></div>)}
              </dl>
              {earlier.length > 0 && (
                <ul className={styles.years} aria-label={`Wcześniejsze lata ${WRAPPER_LABEL[wrapper]}`}>
                  {earlier.map((l) => (
                    <li key={l.year}>
                      <span>{l.year}</span>
                      <span>{l.limit_pln === null ? <>{formatMoney(l.paid_pln)}, <span className="dim">brak limitu w danych</span></>
                        : `${formatMoney(l.paid_pln)} z ${formatMoney(l.limit_pln)}`}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
    </div>
  );
}
