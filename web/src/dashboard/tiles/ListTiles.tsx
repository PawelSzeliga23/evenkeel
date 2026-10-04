/** Plan 9b: the new kinds of tiles — currency exposure, latest operations, best and worst holdings, cash, bonds,
 * savings accounts and the journal. Each says why it is empty instead of standing blank. */
import { useQueries, useQuery } from "@tanstack/react-query";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Holding, Position, Summary } from "../../api/types";
import { formatDate, formatPercent, signOf, sumMoney } from "../../format";
import { ALLOCATION_COLORS } from "../../screens/dashboard/model";
import base from "../../screens/dashboard/Dashboard.module.css";
import { entryLabel, entryLead } from "../../screens/history/model";
import { HOLDINGS_PATH } from "../../screens/holdings/HoldingsCard";
import { holdingLabel } from "../../screens/holdings/HeatMap";
import { Money } from "../../ui/Amount";
import { ListRow } from "../../ui/ListRow";
import { Skeleton } from "../../ui/States";
import styles from "../Dashboard.module.css";
import { widthOf, type Tile } from "../layout";
import { TileBrief, TileError, TileNote, TileSection } from "../parts";

const small = (tile: Tile) => tile.variant.startsWith("S");
const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");
const BASE_CURRENCY = "PLN";
const PERIOD_NAMES = { "1d": "dziś", "1w": "1 tydzień", "1m": "1 miesiąc", "1y": "1 rok", ytd: "od pocz. roku", all: "cały okres" } as const;

/** Loading and a failed request look the same in every tile; null when the data is there. */
function pending(title: string, query: { isPending: boolean; isError: boolean; refetch: () => unknown }) {
  if (query.isPending) return <TileSection title={title}><Skeleton rows={2} /></TileSection>;
  if (query.isError) return <TileSection title={title}><TileError onRetry={() => void query.refetch()} /></TileSection>;
  return null;
}

function usePositions(summary: Summary) {
  const [accountIds, , ready] = useAccountSelection();
  return useQuery({
    queryKey: keys.positions(accountIds), queryFn: () => api.positions(accountIds),
    enabled: ready && summary.as_of !== null, placeholderData: (previous) => previous,
  });
}

export function ExposureTile({ tile, summary }: { tile: Tile<"exposure">; summary: Summary }) {
  const [accountIds, , ready] = useAccountSelection();
  const asOf = summary.as_of;
  const query = useQuery({
    queryKey: keys.exposure(accountIds, asOf ?? ""), queryFn: () => api.exposure(accountIds, asOf!), enabled: ready && asOf !== null,
  });
  const title = "Ekspozycja walutowa";
  const waiting = pending(title, query);
  if (waiting) return waiting;
  const items = query.data!.current.filter((item) => signOf(item.value_pln) > 0);
  if (items.length === 0) return <TileSection title={title}><TileNote>Brak wyceny w wybranych kontach.</TileNote></TileSection>;
  if (small(tile)) {
    const foreign = items.filter((item) => item.currency !== BASE_CURRENCY)
      .sort((a, b) => Number(b.value_pln) - Number(a.value_pln))[0];
    return (
      <TileBrief title={title} to="/ekspozycja"
        value={foreign ? <span className="num">{formatPercent(foreign.share_pct, { sign: false, places: 1 })}</span> : <span className="dim">—</span>}
        note={foreign ? `w ${foreign.currency}` : "Cały portfel w złotych."} />
    );
  }
  return (
    <TileSection title={title} more={{ to: "/ekspozycja", label: "Ekspozycja w czasie", text: "W czasie" }}>
      <div className={base.allocBar} aria-hidden="true">
        {items.map((item, i) => (
          <i key={item.currency} style={{ flex: Number(item.value_pln), background: ALLOCATION_COLORS[i % ALLOCATION_COLORS.length] }} />
        ))}
      </div>
      <div className={styles.tileRows}>
        {items.map((item, i) => (
          <div key={item.currency} className={base.allocRow}>
            <span className={base.dot} style={{ background: ALLOCATION_COLORS[i % ALLOCATION_COLORS.length] }} />
            <span>{item.currency}</span>
            <span className={base.allocAmount}>
              <Money value={item.value_pln} />
              <small className="num dim">{formatPercent(item.share_pct, { sign: false, places: 1 })}</small>
            </span>
          </div>
        ))}
      </div>
    </TileSection>
  );
}

export function OperationsTile({ tile }: { tile: Tile<"operations"> }) {
  const [accountIds, , ready] = useAccountSelection();
  const query = useQuery({
    queryKey: keys.latestEntries(accountIds),
    queryFn: () => api.entries({ account_ids: accountIds, type: null, from: null, to: null, q: "" }, null),
    enabled: ready,
  });
  const title = "Ostatnie operacje";
  const waiting = pending(title, query);
  if (waiting) return waiting;
  const items = query.data!.items;
  if (items.length === 0) return <TileSection title={title}><TileNote>Nie ma jeszcze operacji.</TileNote></TileSection>;
  const amount = (item: (typeof items)[number]) => <Money value={item.amount_pln ?? item.amount} sign tone currency={item.amount_pln === null ? item.currency : null} />;
  if (small(tile)) {
    const last = items[0]!;
    return (
      <TileBrief title={title} to="/historia" value={amount(last)}
        note={`${last.name ?? entryLabel(last)} · ${formatDate(last.date)}`} />
    );
  }
  return (
    <TileSection title={title} more={{ to: "/historia", label: "Cała historia", text: "Historia" }}>
      <div className={styles.tileRows} data-cols={widthOf(tile.variant) === "L" ? 2 : 1}>
        {items.slice(0, tile.settings.count).map((item) => (
          <ListRow key={item.id} lead={entryLead(item)} title={item.name ?? entryLabel(item)}
            subtitle={`${item.name ? `${entryLabel(item)} · ` : ""}${formatDate(item.date)}`} value={amount(item)} />
        ))}
      </div>
    </TileSection>
  );
}

function HoldingRow({ item }: { item: Holding }) {
  return (
    <ListRow lead={holdingLabel(item)} title={item.name}
      value={<span className={`num ${tone(item.gain_pct)}`}>{formatPercent(item.gain_pct, { places: 1 })}</span>}
      detail={<Money value={item.gain_pln} sign />} />
  );
}

export function ExtremesTile({ tile }: { tile: Tile<"extremes"> }) {
  const [accountIds, , ready] = useAccountSelection();
  const { count, period } = tile.settings;
  const query = useQuery({
    queryKey: keys.holdings(accountIds, period), queryFn: () => api.holdings(accountIds, period), enabled: ready,
  });
  const title = "Najlepsze i najgorsze";
  const waiting = pending(title, query);
  if (waiting) return waiting;
  const ranked = query.data!.items.filter((item) => item.gain_pct !== null)
    .sort((a, b) => Number(b.gain_pct) - Number(a.gain_pct));
  if (query.data!.period === null || ranked.length === 0) {
    return <TileSection title={title}><TileNote>Brak wyceny w tym okresie.</TileNote></TileSection>;
  }
  const take = Math.min(small(tile) ? 1 : count, Math.floor(ranked.length / 2) || 1);
  const best = ranked.slice(0, take);
  const worst = ranked.length > 1 ? ranked.slice(-take).reverse() : [];
  if (small(tile)) {
    return (
      <TileBrief title={title} to={HOLDINGS_PATH} note={PERIOD_NAMES[period]} value={(
        <span className={styles.tileBriefPair}>
          {[...best, ...worst].map((item) => (
            <span key={item.key}>
              <span>{holdingLabel(item)}</span>
              <span className={`num ${tone(item.gain_pct)}`}>{formatPercent(item.gain_pct, { places: 1 })}</span>
            </span>
          ))}
        </span>
      )} />
    );
  }
  return (
    <TileSection title={title} more={{ to: HOLDINGS_PATH, label: "Wszystkie walory", text: PERIOD_NAMES[period] }}>
      <div className={styles.tileSides} data-wide={widthOf(tile.variant) === "L" || undefined}>
        <div className={styles.tileRows} aria-label="Najlepsze" role="list">
          {best.map((item) => <div key={item.key} role="listitem"><HoldingRow item={item} /></div>)}
        </div>
        {worst.length > 0 && (
          <div className={styles.tileRows} aria-label="Najgorsze" role="list">
            {worst.map((item) => <div key={item.key} role="listitem"><HoldingRow item={item} /></div>)}
          </div>
        )}
      </div>
    </TileSection>
  );
}

export function CashTile({ tile, summary }: { tile: Tile<"cash">; summary: Summary }) {
  const query = usePositions(summary);
  const title = "Gotówka na kontach";
  if (summary.as_of === null) return <TileSection title={title}><TileNote>Brak wyceny w wybranych kontach.</TileNote></TileSection>;
  const waiting = pending(title, query);
  if (waiting) return waiting;
  const cash = query.data!.filter((p) => p.kind === "cash" && signOf(p.value_pln) !== 0);
  if (small(tile)) {
    return <TileBrief title={title} to="/pozycje" value={<Money value={summary.cash_pln} />}
      note={`na ${cash.length} ${cash.length === 1 ? "pozycji" : "pozycjach"}`} />;
  }
  if (cash.length === 0) return <TileSection title={title}><TileNote>Nie masz wolnej gotówki.</TileNote></TileSection>;
  return (
    <TileSection title={title} more={{ to: "/pozycje", label: "Wszystkie pozycje", text: "Pozycje" }}>
      <div className={styles.tileRows}>
        {cash.map((p) => (
          <ListRow key={`${p.account_id}-${p.currency ?? ""}`} lead={p.currency ?? "zł"} title={p.account_name}
            value={<Money value={p.value_pln} />} />
        ))}
      </div>
    </TileSection>
  );
}

export function BondsTile({ tile }: { tile: Tile<"bonds"> }) {
  const [accountIds] = useAccountSelection();
  const query = useQuery({ queryKey: keys.bonds, queryFn: api.bonds });
  const title = "Obligacje";
  const waiting = pending(title, query);
  if (waiting) return waiting;
  const bonds = query.data!
    .filter((b) => b.status === "active" && (accountIds.length === 0 || accountIds.includes(b.account_id)))
    .sort((a, b) => a.maturity_date.localeCompare(b.maturity_date));
  if (bonds.length === 0) return <TileSection title={title}><TileNote>Nie masz obligacji w wybranych kontach.</TileNote></TileSection>;
  if (small(tile)) {
    return <TileBrief title={title} to="/pozycje" value={<Money value={sumMoney(bonds.map((b) => b.value_pln))} />}
      note={`wykup ${bonds[0]!.series}: ${formatDate(bonds[0]!.maturity_date)}`} />;
  }
  return (
    <TileSection title={title} more={{ to: "/pozycje", label: "Wszystkie pozycje", text: "Pozycje" }}>
      <div className={styles.tileRows}>
        {bonds.map((b) => (
          <ListRow key={b.id} to={`/pozycje/obligacje/${b.id}`} lead={b.bond_type} title={`${b.series} · ${b.quantity} szt.`}
            subtitle={`wykup ${formatDate(b.maturity_date)}`} value={<Money value={b.value_pln} />} />
        ))}
      </div>
    </TileSection>
  );
}

export function SavingsTile({ tile, summary }: { tile: Tile<"savings">; summary: Summary }) {
  const query = usePositions(summary);
  const accounts: Position[] = (query.data ?? []).filter((p) => p.kind === "savings" && p.savings_account_id !== null);
  const details = useQueries({
    queries: accounts.map((p) => ({ queryKey: keys.savings(p.savings_account_id!), queryFn: () => api.savings(p.savings_account_id!) })),
  });
  const title = "Konta oszczędnościowe";
  if (summary.as_of === null) return <TileSection title={title}><TileNote>Brak wyceny w wybranych kontach.</TileNote></TileSection>;
  const waiting = pending(title, query);
  if (waiting) return waiting;
  if (accounts.length === 0) return <TileSection title={title}><TileNote>Nie masz kont oszczędnościowych w wybranych kontach.</TileNote></TileSection>;
  const rate = (i: number) => {
    const current = details[i]?.data?.summary.current_rate ?? null;
    return current === null ? "—" : formatPercent(current, { sign: false });
  };
  if (small(tile)) {
    const largest = accounts.reduce((top, p, i) => (Number(p.value_pln) > Number(accounts[top]!.value_pln) ? i : top), 0);
    return <TileBrief title={title} to={`/pozycje/oszczednosci/${accounts[largest]!.savings_account_id}`}
      value={<Money value={sumMoney(accounts.map((p) => p.value_pln))} />}
      note={accounts.length === 1 ? `${rate(0)} rocznie` : `${accounts[largest]!.account_name}: ${rate(largest)} rocznie`} />;
  }
  return (
    <TileSection title={title} more={{ to: "/pozycje", label: "Wszystkie pozycje", text: "Pozycje" }}>
      <div className={styles.tileRows}>
        {accounts.map((p, i) => {
          const interest = details[i]?.data?.summary.interest_net;
          return (
            <ListRow key={p.savings_account_id} to={`/pozycje/oszczednosci/${p.savings_account_id}`} lead="%"
              title={p.account_name} subtitle={`${rate(i)} rocznie`} value={<Money value={p.value_pln} />}
              detail={interest === undefined ? undefined : <>odsetki <Money value={interest} sign /></>} />
          );
        })}
      </div>
    </TileSection>
  );
}

const JOURNAL_PATH = "/ustawienia/dziennik";

export function JournalTile({ tile }: { tile: Tile<"journal"> }) {
  const query = useQuery({ queryKey: keys.journal("all"), queryFn: () => api.journal(null) });
  const title = "Dziennik";
  const waiting = pending(title, query);
  if (waiting) return waiting;
  const entries = query.data!.entries;
  if (entries.length === 0) return <TileSection title={title}><TileNote>Nie ma jeszcze wpisów w dzienniku.</TileNote></TileSection>;
  if (small(tile)) {
    const last = entries[0]!;
    return <TileBrief title={title} to={JOURNAL_PATH} value={formatDate(last.entry_date)} note={last.body} />;
  }
  return (
    <TileSection title={title} more={{ to: JOURNAL_PATH, label: "Cały dziennik", text: "Dziennik" }}>
      <ul className={styles.tileEntries}>
        {entries.slice(0, 3).map((entry) => (
          <li key={entry.id}>
            <small className="dim">{`${formatDate(entry.entry_date)}${entry.target ? ` · ${entry.target.label}` : ""}`}</small>
            <span>{entry.body}</span>
          </li>
        ))}
      </ul>
    </TileSection>
  );
}
