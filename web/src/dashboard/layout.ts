/** Plan 9: the Pulpit as an ordered list of tiles; one layout for the phone and the computer. */
import type { AnalyticsPeriod, Preferences } from "../api/types";
import { METRIC_KEYS, type MetricKey } from "./metrics";

export type TileSize = "S" | "M" | "L";
export type ValueRange = Preferences["value_range"];
export type PriceRange = Preferences["price_range"];
export type AllocationBy = "kind" | "account" | "currency";

export interface TileSettings {
  summary: { fields: MetricKey[] };
  metric: { metric: MetricKey };
  value_chart: { range: ValueRange };
  price_chart: { account_id: number | null; instrument_id: number | null; range: PriceRange };
  allocation: { by: AllocationBy };
  analysis: { metrics: MetricKey[]; period: AnalyticsPeriod };
  limits: Record<string, never>;
  movers: { count: 3 | 5 | 10 };
  holdings: Record<string, never>;
  income: Record<string, never>;
  tags: Record<string, never>;
  simulator: Record<string, never>;
  review: Record<string, never>;
}
export type TileKind = keyof TileSettings;
export type Tile<K extends TileKind = TileKind> = K extends TileKind
  ? { id: string; kind: K; size: TileSize; settings: TileSettings[K] } : never;
export interface DashboardLayout { version: 1; tiles: Tile[] }

export const MAX_TILES = 40;
export const VALUE_RANGES: readonly ValueRange[] = ["1M", "3M", "1R", "ALL"];
export const PRICE_RANGES: readonly PriceRange[] = ["buy", "6m", "1y", "5y", "max"];
export const ANALYSIS_PERIODS: readonly AnalyticsPeriod[] = ["1m", "3m", "1y", "ytd", "all"];
const ALLOCATION_BY: readonly AllocationBy[] = ["kind", "account", "currency"];
const MOVER_COUNTS = [3, 5, 10] as const;

type Check<K extends TileKind> = (settings: Record<string, unknown>) => settings is TileSettings[K] & Record<string, unknown>;

interface KindInfo<K extends TileKind> {
  name: string;
  description: string;
  sizes: TileSize[];
  defaults: () => TileSettings[K];
  valid: Check<K>;
}

const isId = (v: unknown) => v === null || (typeof v === "number" && Number.isInteger(v) && v >= 1);
const isMetric = (v: unknown): v is MetricKey => typeof v === "string" && (METRIC_KEYS as readonly string[]).includes(v);
const metricList = (v: unknown, max: number) => Array.isArray(v) && v.length >= 1 && v.length <= max && v.every(isMetric);
const oneOf = <T>(list: readonly T[], v: unknown) => list.includes(v as T);
const only = (s: Record<string, unknown>, keys: string[]) => Object.keys(s).every((k) => keys.includes(k));
const none = ((s: Record<string, unknown>) => Object.keys(s).length === 0) as Check<"limits">;
type CardKind = "holdings" | "income" | "tags" | "simulator" | "review";
const card = <K extends CardKind>(name: string, description: string): KindInfo<K> => ({
  name, description, sizes: ["M"], defaults: () => ({}) as TileSettings[K], valid: none as unknown as Check<K>,
});

export const KINDS: { [K in TileKind]: KindInfo<K> } = {
  summary: {
    name: "Wartość portfela", description: "Kwota, zmiana dziś i cztery wybrane miary.", sizes: ["M", "L"],
    defaults: () => ({ fields: ["total_gain", "twr_total", "invested", "income"] }),
    valid: ((s) => only(s, ["fields"]) && metricList(s.fields, 4)) as Check<"summary">,
  },
  metric: {
    name: "Jedna miara", description: "Jedna liczba, np. XIRR albo Sharpe.", sizes: ["S"],
    defaults: () => ({ metric: "xirr" }),
    valid: ((s) => only(s, ["metric"]) && isMetric(s.metric)) as Check<"metric">,
  },
  value_chart: {
    name: "Wykres wartości", description: "Wartość portfela w czasie.", sizes: ["M", "L"],
    defaults: () => ({ range: "1R" }),
    valid: ((s) => only(s, ["range"]) && oneOf(VALUE_RANGES, s.range)) as Check<"value_chart">,
  },
  price_chart: {
    name: "Wykres ceny", description: "Cena jednego waloru z Twoimi zakupami i sprzedażami.", sizes: ["M", "L"],
    defaults: () => ({ account_id: null, instrument_id: null, range: "buy" }),
    valid: ((s) => only(s, ["account_id", "instrument_id", "range"]) && isId(s.account_id ?? null)
      && isId(s.instrument_id ?? null) && oneOf(PRICE_RANGES, s.range)) as Check<"price_chart">,
  },
  allocation: {
    name: "Alokacja", description: "Podział portfela według typu, konta albo waluty.", sizes: ["S", "L"],
    defaults: () => ({ by: "kind" }),
    valid: ((s) => only(s, ["by"]) && oneOf(ALLOCATION_BY, s.by)) as Check<"allocation">,
  },
  analysis: {
    name: "Analiza", description: "Wybrane miary za wybrany okres.", sizes: ["M", "L"],
    defaults: () => ({ metrics: ["xirr", "max_drawdown"], period: "all" }),
    valid: ((s) => only(s, ["metrics", "period"]) && metricList(s.metrics, 6)
      && oneOf(ANALYSIS_PERIODS, s.period)) as Check<"analysis">,
  },
  limits: { name: "Limity IKE/IKZE", description: "Wpłaty w tym roku wobec limitu.", sizes: ["M"], defaults: () => ({}), valid: none },
  movers: {
    name: "Dziś najbardziej", description: "Walory, które dziś najbardziej się zmieniły.", sizes: ["M", "L"],
    defaults: () => ({ count: 5 }),
    valid: ((s) => only(s, ["count"]) && oneOf(MOVER_COUNTS, s.count)) as Check<"movers">,
  },
  holdings: card("Walory", "Mała mapa cieplna walorów."),
  income: card("Dochód i koszty", "Dochód pasywny i koszty."),
  tags: card("Tagi", "Udział i zysk Twoich tagów."),
  simulator: card("Symulator", "Ostatnie scenariusze „co by było, gdyby”."),
  review: card("Przegląd AI", "Skrót ostatniego przeglądu portfela."),
};

export const KIND_ORDER = Object.keys(KINDS) as TileKind[];

function tile<K extends TileKind>(id: string, kind: K, size: TileSize, settings?: TileSettings[K]): Tile {
  return { id, kind, size, settings: settings ?? KINDS[kind].defaults() } as Tile;
}

export const DEFAULT_LAYOUT: DashboardLayout = {
  version: 1,
  tiles: [
    tile("summary", "summary", "L"),
    tile("value", "value_chart", "L"),
    tile("allocation", "allocation", "L"),
    tile("analysis", "analysis", "M"),
    tile("limits", "limits", "M"),
    tile("movers", "movers", "L"),
  ],
};

function validTile(raw: unknown, seen: Set<string>): raw is Tile {
  if (typeof raw !== "object" || raw === null) return false;
  const t = raw as Record<string, unknown>;
  if (typeof t.id !== "string" || !/^[A-Za-z0-9_-]{1,20}$/.test(t.id) || seen.has(t.id)) return false;
  if (typeof t.kind !== "string" || !(t.kind in KINDS)) return false;
  const info = KINDS[t.kind as TileKind] as KindInfo<TileKind>;
  if (!info.sizes.includes(t.size as TileSize)) return false;
  const settings = t.settings;
  return typeof settings === "object" && settings !== null && info.valid(settings as Record<string, unknown>);
}

/** The stored layout, without tiles this version cannot show; none stored (or another version) → the default. */
export function normalize(stored: unknown): DashboardLayout {
  if (typeof stored !== "object" || stored === null) return DEFAULT_LAYOUT;
  const { version, tiles } = stored as { version?: unknown; tiles?: unknown };
  if (version !== 1 || !Array.isArray(tiles)) return DEFAULT_LAYOUT;
  const seen = new Set<string>();
  const kept: Tile[] = [];
  for (const raw of tiles.slice(0, MAX_TILES)) {
    if (validTile(raw, seen)) {
      seen.add(raw.id);
      kept.push(raw);
    }
  }
  return { version: 1, tiles: kept };
}

export function newTileId(): string {
  return `t${Math.random().toString(36).slice(2, 10)}`;
}

/** A new tile of `kind` goes first, where it is seen; at the limit nothing is added. */
export function addTile(layout: DashboardLayout, kind: TileKind, id = newTileId()): DashboardLayout {
  if (layout.tiles.length >= MAX_TILES) return layout;
  return { ...layout, tiles: [tile(id, kind, KINDS[kind].sizes[KINDS[kind].sizes.length - 1]!), ...layout.tiles] };
}

export function removeTile(layout: DashboardLayout, id: string): DashboardLayout {
  return { ...layout, tiles: layout.tiles.filter((t) => t.id !== id) };
}

export function moveTile(layout: DashboardLayout, id: string, toIndex: number): DashboardLayout {
  const from = layout.tiles.findIndex((t) => t.id === id);
  if (from < 0) return layout;
  const tiles = [...layout.tiles];
  const [moved] = tiles.splice(from, 1);
  tiles.splice(Math.max(0, Math.min(toIndex, tiles.length)), 0, moved!);
  return { ...layout, tiles };
}

export function updateTile(layout: DashboardLayout, id: string, patch: Partial<Pick<Tile, "size" | "settings">>): DashboardLayout {
  return { ...layout, tiles: layout.tiles.map((t) => (t.id === id ? ({ ...t, ...patch } as Tile) : t)) };
}

export function sameLayout(a: DashboardLayout, b: DashboardLayout): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
