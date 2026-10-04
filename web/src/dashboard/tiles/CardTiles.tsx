/** Plan 9: the cards of Analiza (and the IKE/IKZE limits) as tiles. A card hides itself without data; the tile asks
 * the same query (one request, shared by key) to say why instead of standing empty. Plan 9b: a small variant (S)
 * shows the one thing that matters from the same data. */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { formatPercent, formatRefreshed, pluralPl } from "../../format";
import { HoldingsCard } from "../../screens/holdings/HoldingsCard";
import { INCOME_PATH, IncomeCard } from "../../screens/income/IncomeCard";
import { LimitsCard } from "../../screens/limits/LimitsCard";
import { WRAPPER_LABEL, byWrapper, filled } from "../../screens/limits/model";
import { ReviewCard } from "../../screens/review/ReviewCard";
import { SimulatorCard } from "../../screens/simulator/SimulatorCard";
import { useScenarioResults } from "../../screens/simulator/SimulatorScreen";
import { difference } from "../../screens/simulator/model";
import { TagsCard } from "../../screens/tags/TagsCard";
import { TAGS_PATH } from "../../screens/tags/model";
import { Money } from "../../ui/Amount";
import { Skeleton } from "../../ui/States";
import styles from "../Dashboard.module.css";
import type { Tile } from "../layout";
import { TileBrief, TileError, TileNote, TileSection } from "../parts";

function CardTile({ title, query, empty, card }: {
  title: string; query: UseQueryResult<unknown>; empty: string | null; card: ReactNode;
}) {
  if (query.isPending) return <TileSection title={title}><Skeleton rows={2} /></TileSection>;
  if (query.isError) return <TileSection title={title}><TileError onRetry={() => void query.refetch()} /></TileSection>;
  if (empty !== null) return <TileSection title={title}><TileNote>{empty}</TileNote></TileSection>;
  return <>{card}</>;
}

const NO_VALUATION = "Wybrane konta nie mają jeszcze wyceny.";
const small = (tile: Tile) => tile.variant.startsWith("S");

export function LimitsTile({ tile }: { tile: Tile<"limits"> }) {
  const query = useQuery({ queryKey: keys.limits, queryFn: api.limits });
  const brief = small(tile) && query.data && query.data.length > 0 ? (
    <TileBrief title="Limity IKE/IKZE" to="/limity" value={(
      <span className={styles.tileBriefPair}>
        {byWrapper(query.data).map(({ wrapper, current }) => {
          const share = filled(current);
          return (
            <span key={wrapper}>
              <span>{`${WRAPPER_LABEL[wrapper]} ${current.year}`}</span>
              <span className={`num ${current.exceeded ? "down" : ""}`}>
                {share === null ? "—" : formatPercent((share * 100).toFixed(1), { sign: false, places: 0 })}
              </span>
            </span>
          );
        })}
      </span>
    )} />
  ) : null;
  return <CardTile title="Limity IKE/IKZE" query={query} card={brief ?? <LimitsCard />}
    empty={query.data?.length === 0 ? "Nie masz kont IKE ani IKZE." : null} />;
}

const HEATMAP_HEIGHT: Record<string, number> = { S3: 160, M3: 140, L5: 340 };

export function HoldingsTile({ tile }: { tile: Tile<"holdings"> }) {
  const [accountIds, , ready] = useAccountSelection();
  const query = useQuery({ queryKey: keys.holdings(accountIds, "1d"), queryFn: () => api.holdings(accountIds, "1d"), enabled: ready });
  return <CardTile title="Walory" query={query}
    card={<HoldingsCard height={HEATMAP_HEIGHT[tile.variant] ?? 140} labels={!small(tile)} />}
    empty={query.data?.period === null ? NO_VALUATION : null} />;
}

export function IncomeTile({ tile }: { tile: Tile<"income"> }) {
  const [accountIds, , ready] = useAccountSelection();
  const query = useQuery({ queryKey: keys.income(accountIds, "ytd"), queryFn: () => api.income(accountIds, "ytd"), enabled: ready });
  const data = query.data;
  const brief = small(tile) && data && data.period !== null
    ? <TileBrief title="Dochód i koszty" to={INCOME_PATH} value={<Money value={data.totals.balance_pln} sign tone />}
      note="bilans od pocz. roku" />
    : null;
  return <CardTile title="Dochód i koszty" query={query} card={brief ?? <IncomeCard />}
    empty={data?.period === null ? NO_VALUATION : null} />;
}

export function TagsTile({ tile }: { tile: Tile<"tags"> }) {
  const [accountIds, , ready] = useAccountSelection();
  const query = useQuery({
    queryKey: keys.tagAnalytics(accountIds, "all"), queryFn: () => api.tagAnalytics(accountIds, "all"), enabled: ready,
  });
  const top = query.data?.tags[0];
  const brief = small(tile) && query.data ? (
    top ? <TileBrief title="Tagi" to={TAGS_PATH} value={top.name}
      note={<span className="num">{`${formatPercent(top.share_pct, { sign: false })} portfela`}</span>} />
      : <TileBrief title="Tagi" to={TAGS_PATH} value={<span className="dim">—</span>} note="Brak otagowanych walorów." />
  ) : null;
  return <CardTile title="Tagi" query={query} card={brief ?? <TagsCard />} empty={null} />;
}

function SimulatorBrief() {
  const scenarios = useQuery({ queryKey: keys.scenarios, queryFn: api.scenarios });
  const latest = (scenarios.data ?? []).slice(0, 3);
  const results = useScenarioResults(latest, "all");
  const scored = latest.flatMap((scenario, i) => {
    const result = results[i]?.data;
    if (!result?.portfolio || !result.scenario) return [];
    return [{ scenario, result, gain: Number(result.scenario.value_pln) - Number(result.portfolio.value_pln) }];
  });
  const best = scored.sort((a, b) => b.gain - a.gain)[0];
  if (latest.length === 0) {
    return <TileBrief title="Symulator" to="/analiza/symulator" value={<span className="dim">—</span>} note="Nie ma jeszcze scenariuszy." />;
  }
  return (
    <TileBrief title="Symulator" to="/analiza/symulator" value={best ? best.scenario.name : <span className="dim">liczę…</span>}
      note={best ? difference(best.result) ?? undefined : undefined} />
  );
}

export function SimulatorTile({ tile }: { tile: Tile<"simulator"> }) {
  const query = useQuery({ queryKey: keys.scenarios, queryFn: api.scenarios });
  return <CardTile title="Symulator" query={query} card={small(tile) ? <SimulatorBrief /> : <SimulatorCard />} empty={null} />;
}

export function ReviewTile({ tile }: { tile: Tile<"review"> }) {
  const query = useQuery({ queryKey: keys.reviews, queryFn: api.reviews });
  const latest = query.data?.[0];
  const brief = small(tile) && query.data ? (
    <TileBrief title="Przegląd AI" to="/analiza/przeglad"
      value={latest ? formatRefreshed(latest.created_at) : <span className="dim">—</span>}
      note={latest ? `${latest.sections} ${pluralPl(latest.sections, "sekcja", "sekcje", "sekcji")}` : "Jeszcze nie ma przeglądu."} />
  ) : null;
  return <CardTile title="Przegląd AI" query={query} card={brief ?? <ReviewCard />} empty={null} />;
}
