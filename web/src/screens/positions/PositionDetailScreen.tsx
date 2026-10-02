import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, Navigate, useParams } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { PositionDetail, Reconciliation } from "../../api/types";
import { formatDate, formatDateTime, formatDays, formatDecimal, formatPercent, signOf } from "../../format";
import { HeroAmount, Money } from "../../ui/Amount";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { PriceSection } from "./PriceSection";
import { transactionLabel } from "./model";
import styles from "./Positions.module.css";

function Back() {
  return (
    <Link className={styles.back} to="/pozycje">
      <svg width="10" height="14" viewBox="0 0 10 14" aria-hidden="true">
        <path d="M8 1 2 7l6 6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      Pozycje
    </Link>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = `section-${title.replace(/\s+/g, "-")}`;
  return (
    <section className={ui.section} aria-labelledby={id}>
      <h2 id={id} className={ui.sectionTitle}>{title}</h2>
      {children}
    </section>
  );
}

function Entry({ title, subtitle, value, detail }: { title: ReactNode; subtitle?: ReactNode; value: ReactNode; detail?: ReactNode }) {
  return (
    <li className={styles.entry}>
      <span className={styles.entryName}><b>{title}</b>{subtitle && <small>{subtitle}</small>}</span>
      <span className={styles.entryAmount}><span>{value}</span>{detail && <small>{detail}</small>}</span>
    </li>
  );
}

const price = (value: string | null, currency: string | null) =>
  value === null ? "—" : `${formatDecimal(value, 4)}${currency ? `\u00a0${currency}` : " w walucie instrumentu"}`;

/** An exit cost (a positive amount) shown as money taken away. */
const minus = (value: string) => (signOf(value) > 0 ? `-${value}` : value);

function reconciliationText(r: Reconciliation): { title: string; subtitle: string; tone: string } {
  const when = r.taken_at ? `stan z ${formatDateTime(r.taken_at)}` : "";
  if (r.status === "ok") return { title: "Zgodne z XTB", subtitle: when, tone: "up" };
  if (r.status === "mismatch") {
    const xtb = r.xtb_quantity === null ? "—" : formatDecimal(r.xtb_quantity, 8);
    const calculated = r.calculated_quantity === null ? "—" : formatDecimal(r.calculated_quantity, 8);
    return { title: "Niezgodność z XTB", subtitle: `XTB: ${xtb}\u00a0szt., wyliczone: ${calculated}\u00a0szt., ${when}`, tone: "down" };
  }
  return { title: "Brak stanu z XTB do porównania", subtitle: "Wgraj eksport z zakładką Open Positions.", tone: "dim" };
}

function Detail({ detail, accountId, instrumentId }: { detail: PositionDetail; accountId: number; instrumentId: number }) {
  const p = detail.position;
  const check = reconciliationText(detail.reconciliation);
  const gainTone = signOf(p.unrealized_pln) > 0 ? "up" : signOf(p.unrealized_pln) < 0 ? "down" : "";
  const source = p.price_source === "xtb" ? "z XTB" : "od dostawcy";
  return (
    <>
      <section className={styles.head} aria-label="Podsumowanie pozycji">
        <span className="dim">{[p.ticker, p.account_name].filter(Boolean).join(", ")}</span>
        <h1 className={styles.name}>{p.name}</h1>
        <HeroAmount value={p.payout_pln} size="m" />
        <p className={`num ${gainTone}`}>
          <Money value={p.unrealized_pln} sign /> ({formatPercent(p.unrealized_pct)})
        </p>
      </section>

      <PriceSection accountId={accountId} instrumentId={instrumentId}
        average={signOf(p.quantity) > 0 ? detail.average_price : null} />

      <Section title="Podsumowanie">
        <dl className={ui.kv}>
          <dt>Ilość</dt><dd>{`${formatDecimal(p.quantity, 8)}\u00a0szt.`}</dd>
          <dt>Cena</dt><dd>{price(p.price, p.price_currency)}</dd>
          {detail.average_price !== null && <><dt>Średnia cena</dt><dd>{price(detail.average_price, p.currency)}</dd></>}
          {p.price_date && <><dt>Źródło ceny</dt><dd>{`${source}, ${formatDate(p.price_date)}`}</dd></>}
          <dt>Koszt</dt><dd><Money value={p.cost_pln} /></dd>
          {p.share_pct !== null && <><dt>Udział w portfelu</dt><dd>{formatPercent(p.share_pct, { sign: false, places: 1 })}</dd></>}
        </dl>
      </Section>

      {signOf(p.exit_cost_pln) > 0 && (
        <Section title="Do wypłaty">
          <dl className={ui.kv}>
            <dt>Wartość rynkowa</dt><dd><Money value={p.value_pln} /></dd>
            {signOf(p.exit_fx_pln) > 0 && <><dt>Przewalutowanie XTB 0,5 %</dt><dd><Money value={minus(p.exit_fx_pln)} /></dd></>}
            {signOf(p.exit_spread_pln) > 0 && (
              <><dt>{`Spread (ręczny ${formatDecimal(p.spread_pct ?? "0", 4)} %)`}</dt><dd><Money value={minus(p.exit_spread_pln)} /></dd></>
            )}
            <dt>Do wypłaty</dt><dd><Money value={p.payout_pln} /></dd>
          </dl>
        </Section>
      )}

      <Section title="Zysk">
        <dl className={ui.kv}>
          <dt>Zmiana ceny</dt><dd><Money value={p.price_effect_pln} sign tone /></dd>
          <dt>Kurs waluty</dt><dd><Money value={p.fx_effect_pln} sign tone /></dd>
          {signOf(p.exit_cost_pln) > 0 && <><dt>Koszty wyjścia</dt><dd><Money value={minus(p.exit_cost_pln)} sign tone /></dd></>}
          <dt>Dywidendy</dt><dd><Money value={p.dividends_net_pln} sign tone /></dd>
          <dt>Koszty</dt><dd><Money value={p.fees_pln} sign tone /></dd>
          <dt>Zrealizowany</dt><dd><Money value={p.realized_pln} sign tone /></dd>
        </dl>
      </Section>

      <Section title="Partie">
        <ul className={styles.list}>
          {detail.lots.map((lot, i) => (
            <Entry
              key={lot.position_id ?? i}
              title={formatDate(lot.opened_on)}
              subtitle={lot.open_price === null
                ? `${formatDecimal(lot.quantity, 8)}\u00a0szt.`
                : `${formatDecimal(lot.quantity, 8)}\u00a0szt. po ${price(lot.open_price, p.currency)}`}
              value={<Money value={lot.gain_pln} sign tone />}
              detail={[
                formatDays(lot.holding_days),
                lot.open_price_with_fx ? `z przewalutowaniem XTB ${price(lot.open_price_with_fx, p.currency)}` : "",
                lot.stop_loss ? `SL ${formatDecimal(lot.stop_loss, 4)}` : "",
                lot.take_profit ? `TP ${formatDecimal(lot.take_profit, 4)}` : "",
              ].filter(Boolean).join(", ")}
            />
          ))}
        </ul>
      </Section>

      {detail.sales.length > 0 && (
        <Section title="Sprzedaże">
          <ul className={styles.list}>
            {detail.sales.map((sale, i) => (
              <Entry key={i} title={formatDate(sale.date)} subtitle={`${formatDecimal(sale.quantity, 8)}\u00a0szt., ${formatDays(sale.holding_days)}`}
                value={<Money value={sale.realized_pln} sign tone />} detail={<Money value={sale.proceeds_pln} />} />
            ))}
          </ul>
        </Section>
      )}

      {detail.income.length > 0 && (
        <Section title="Dywidendy i odsetki">
          <ul className={styles.list}>
            {detail.income.map((item, i) => (
              <Entry key={i} title={formatDate(item.date)} subtitle={transactionLabel(item.type)}
                value={<Money value={item.amount_pln} sign tone />} />
            ))}
          </ul>
        </Section>
      )}

      <Section title="Operacje">
        <ul className={styles.list}>
          {detail.transactions.map((t) => (
            <Entry key={t.id} title={transactionLabel(t.type)} subtitle={formatDateTime(t.occurred_at)}
              value={<Money value={t.amount} sign currency={t.currency} />}
              detail={t.quantity ? `${formatDecimal(t.quantity, 8)}\u00a0szt.` : undefined} />
          ))}
        </ul>
      </Section>

      <Section title="Zgodność z XTB">
        <p className={check.tone}>{check.title}</p>
        {check.subtitle && <p className="dim">{check.subtitle}</p>}
      </Section>
    </>
  );
}

export function PositionDetailScreen() {
  const params = useParams();
  const accountId = Number(params.accountId);
  const instrumentId = Number(params.instrumentId);
  const valid = Number.isInteger(accountId) && Number.isInteger(instrumentId);
  const detail = useQuery({
    queryKey: keys.position(accountId, instrumentId),
    queryFn: () => api.position(accountId, instrumentId),
    enabled: valid,
  });
  if (!valid) return <Navigate to="/pozycje" replace />;

  return (
    <div className={ui.page}>
      <Back />
      {detail.isPending ? <Skeleton rows={6} />
        : detail.isError ? <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
          : <Detail detail={detail.data} accountId={accountId} instrumentId={instrumentId} />}
    </div>
  );
}
