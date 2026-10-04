/** Plan 9: the cards of Analiza (and the IKE/IKZE limits) as tiles. A card hides itself without data; the tile asks
 * the same query (one request, shared by key) to say why instead of standing empty. */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { HoldingsCard } from "../../screens/holdings/HoldingsCard";
import { IncomeCard } from "../../screens/income/IncomeCard";
import { LimitsCard } from "../../screens/limits/LimitsCard";
import { ReviewCard } from "../../screens/review/ReviewCard";
import { SimulatorCard } from "../../screens/simulator/SimulatorCard";
import { TagsCard } from "../../screens/tags/TagsCard";
import { Skeleton } from "../../ui/States";
import { TileError, TileNote, TileSection } from "../parts";

function CardTile({ title, query, empty, card }: {
  title: string; query: UseQueryResult<unknown>; empty: string | null; card: ReactNode;
}) {
  if (query.isPending) return <TileSection title={title}><Skeleton rows={2} /></TileSection>;
  if (query.isError) return <TileSection title={title}><TileError onRetry={() => void query.refetch()} /></TileSection>;
  if (empty !== null) return <TileSection title={title}><TileNote>{empty}</TileNote></TileSection>;
  return <>{card}</>;
}

const NO_VALUATION = "Wybrane konta nie mają jeszcze wyceny.";

export function LimitsTile() {
  const query = useQuery({ queryKey: keys.limits, queryFn: api.limits });
  return <CardTile title="Limity IKE/IKZE" query={query} card={<LimitsCard />}
    empty={query.data?.length === 0 ? "Nie masz kont IKE ani IKZE." : null} />;
}

export function HoldingsTile() {
  const [accountIds, , ready] = useAccountSelection();
  const query = useQuery({ queryKey: keys.holdings(accountIds, "1d"), queryFn: () => api.holdings(accountIds, "1d"), enabled: ready });
  return <CardTile title="Walory" query={query} card={<HoldingsCard />}
    empty={query.data?.period === null ? NO_VALUATION : null} />;
}

export function IncomeTile() {
  const [accountIds, , ready] = useAccountSelection();
  const query = useQuery({ queryKey: keys.income(accountIds, "ytd"), queryFn: () => api.income(accountIds, "ytd"), enabled: ready });
  return <CardTile title="Dochód i koszty" query={query} card={<IncomeCard />}
    empty={query.data?.period === null ? NO_VALUATION : null} />;
}

export function TagsTile() {
  const [accountIds, , ready] = useAccountSelection();
  const query = useQuery({
    queryKey: keys.tagAnalytics(accountIds, "all"), queryFn: () => api.tagAnalytics(accountIds, "all"), enabled: ready,
  });
  return <CardTile title="Tagi" query={query} card={<TagsCard />} empty={null} />;
}

export function SimulatorTile() {
  const query = useQuery({ queryKey: keys.scenarios, queryFn: api.scenarios });
  return <CardTile title="Symulator" query={query} card={<SimulatorCard />} empty={null} />;
}

export function ReviewTile() {
  const query = useQuery({ queryKey: keys.reviews, queryFn: api.reviews });
  return <CardTile title="Przegląd AI" query={query} card={<ReviewCard />} empty={null} />;
}
