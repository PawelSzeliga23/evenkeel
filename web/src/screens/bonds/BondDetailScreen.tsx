import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { BondDetail } from "../../api/types";
import { formatDate, formatPercent, todayIso } from "../../format";
import { HeroAmount, Money } from "../../ui/Amount";
import { Confirm, Field, FormError, formErrors, useInvalidateAfterSave } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { TagsSection } from "../../tags/TagsSection";
import styles from "./Details.module.css";

const STATUS = { active: "Aktywna", redeemed: "Wykupiona przed terminem", matured: "Wykupiona w terminie" } as const;

export function Back() {
  return (
    <Link className={styles.back} to="/pozycje">
      <svg width="10" height="14" viewBox="0 0 10 14" aria-hidden="true">
        <path d="M8 1 2 7l6 6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      Pozycje
    </Link>
  );
}

function Detail({ detail }: { detail: BondDetail }) {
  const { bond } = detail;
  const navigate = useNavigate();
  const invalidate = useInvalidateAfterSave();
  const queryClient = useQueryClient();
  const [panel, setPanel] = useState<"none" | "redeem" | "delete">("none");
  const [day, setDay] = useState(todayIso());
  const [error, setError] = useState<string | null>(null);

  const redeem = useMutation({
    mutationFn: (redeemedAt: string | null) => api.redeemBond(bond.id, redeemedAt),
    onSuccess: async () => { setPanel("none"); setError(null); await invalidate(); },
    onError: (err) => setError(formErrors(err).general ?? Object.values(formErrors(err).fields)[0] ?? null),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteBond(bond.id),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: keys.bond(bond.id) });
      navigate("/pozycje");
      await invalidate();
    },
    onError: (err) => setError(formErrors(err).general),
  });

  return (
    <>
      <section className={styles.head} aria-label="Podsumowanie obligacji">
        <span className="dim">{`${bond.account_name}, ${bond.quantity} szt., ${STATUS[bond.status]}`}</span>
        <h1 className={styles.name}>{bond.series}</h1>
        <HeroAmount value={bond.value_pln} size="m" />
        <span className="dim">Wartość bieżąca netto</span>
      </section>

      <TagsSection tags={detail.tags} target={{ bond_series: bond.series }} accountId={bond.account_id}
        accountName={bond.account_name} />

      <dl className={ui.kv}>
        <dt>Wartość przy wykupie dziś</dt>
        <dd>{detail.redemption_today_pln === null ? "—" : <Money value={detail.redemption_today_pln} />}</dd>
        <dt>Wartość jednej obligacji</dt><dd><Money value={detail.value_per_bond} /></dd>
        <dt>Data zakupu</dt><dd>{formatDate(bond.purchase_date)}</dd>
        <dt>{bond.redeemed_at ? "Wykup przed terminem" : "Wykup"}</dt>
        <dd>{formatDate(bond.redeemed_at ?? bond.maturity_date)}</dd>
      </dl>

      <section className={ui.section} aria-labelledby="bond-periods">
        <h2 id="bond-periods" className={ui.sectionTitle}>Okresy odsetkowe</h2>
        <ul className={styles.list}>
          {detail.periods.map((period) => (
            <li key={period.number} className={styles.entry}>
              <span className={styles.entryName}>
                <b>{`${period.number}. rok`}</b>
                <small>{`${formatDate(period.start)} – ${formatDate(period.end)}`}</small>
              </span>
              <span className={styles.entryAmount}>
                <span className="num">{`${formatPercent(period.rate, { sign: false })}${period.estimated ? ", szacunkowa" : ""}`}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <div className={styles.actions}>
        {bond.status === "active" && (
          <button type="button" className={ui.secondary} onClick={() => setPanel("redeem")}>Wykup przed terminem</button>
        )}
        {bond.status === "redeemed" && (
          <button type="button" className={ui.secondary} disabled={redeem.isPending} onClick={() => redeem.mutate(null)}>Cofnij wykup</button>
        )}
        <button type="button" className={forms.danger} onClick={() => setPanel("delete")}>Usuń zakup</button>
      </div>

      {panel === "redeem" && (
        <div className={styles.panel}>
          <Field id="bond-redeem-date" label="Data wykupu">
            <input id="bond-redeem-date" type="date" value={day} min={bond.purchase_date} max={todayIso()}
              onChange={(e) => setDay(e.target.value)} />
          </Field>
          <div className={styles.actions}>
            <button type="button" className={ui.primaryButton} disabled={redeem.isPending} onClick={() => redeem.mutate(day)}>Zapisz wykup</button>
            <button type="button" className={forms.cancel} onClick={() => setPanel("none")}>Anuluj</button>
          </div>
        </div>
      )}
      {panel === "delete" && (
        <Confirm
          question={`Usunąć zakup ${bond.quantity} obligacji ${bond.series} z ${formatDate(bond.purchase_date)}?`}
          confirmLabel="Usuń" busy={remove.isPending} onConfirm={() => remove.mutate()} onCancel={() => setPanel("none")}
        />
      )}
      <FormError message={error} />
    </>
  );
}

export function BondDetailScreen() {
  const id = Number(useParams().holdingId);
  const detail = useQuery({ queryKey: keys.bond(id), queryFn: () => api.bond(id), enabled: Number.isInteger(id) });
  return (
    <div className={ui.page}>
      <Back />
      {!Number.isInteger(id) ? <p role="alert">Nie znaleziono obligacji.</p>
        : detail.isPending ? <Skeleton rows={6} />
        : detail.isError ? <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
          : <Detail detail={detail.data} />}
    </div>
  );
}
