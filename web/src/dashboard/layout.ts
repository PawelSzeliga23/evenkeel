/** Plan 9: the Pulpit as an ordered list of tiles; one layout for the phone and the computer.
 * Plan 9b: a tile has a variant — its width (S, M, L) and, on a computer, its height in U; a variant without a digit
 * grows with the fields the owner chose (`heightOf`). */
import type { AnalyticsPeriod, HoldingsPeriod, Preferences } from "../api/types";
import { METRIC_KEYS, type MetricKey } from "./metrics";

export type TileWidth = "S" | "M" | "L";
export type TileVariant = string;
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
  exposure: Record<string, never>;
  operations: { count: 3 | 5 | 10 };
  extremes: { count: 2 | 3 | 5; period: HoldingsPeriod };
  cash: Record<string, never>;
  bonds: Record<string, never>;
  savings: Record<string, never>;
  journal: Record<string, never>;
}
export type TileKind = keyof TileSettings;
export type Tile<K extends TileKind = TileKind> = K extends TileKind
  ? { id: string; kind: K; variant: TileVariant; settings: TileSettings[K] } : never;
export interface DashboardLayout { version: 1; tiles: Tile[] }

export const MAX_TILES = 40;
export const MAX_SUMMARY_FIELDS = 8;
export const ANALYSIS_SMALL_METRICS = 3;
export const VALUE_RANGES: readonly ValueRange[] = ["1M", "3M", "1R", "ALL"];
export const PRICE_RANGES: readonly PriceRange[] = ["buy", "6m", "1y", "5y", "max"];
export const ANALYSIS_PERIODS: readonly AnalyticsPeriod[] = ["1m", "3m", "1y", "ytd", "all"];
export const HOLDINGS_PERIODS: readonly HoldingsPeriod[] = ["1d", "1w", "1m", "1y", "ytd", "all"];
const ALLOCATION_BY: readonly AllocationBy[] = ["kind", "account", "currency"];
export const ROW_COUNTS = [3, 5, 10] as const;
export const EXTREME_COUNTS = [2, 3, 5] as const;

type Check<K extends TileKind> = (settings: Record<string, unknown>) => settings is TileSettings[K] & Record<string, unknown>;

interface KindInfo<K extends TileKind> {
  name: string;
  description: string;
  /** The variants this kind offers, from the smallest; the last one is what a new tile starts as. */
  variants: readonly TileVariant[];
  defaults: () => TileSettings[K];
  valid: Check<K>;
}

const isId = (v: unknown) => v === null || (typeof v === "number" && Number.isInteger(v) && v >= 1);
const isMetric = (v: unknown): v is MetricKey => typeof v === "string" && (METRIC_KEYS as readonly string[]).includes(v);
const metricList = (v: unknown, max: number) => Array.isArray(v) && v.length >= 1 && v.length <= max && v.every(isMetric);
const oneOf = <T>(list: readonly T[], v: unknown) => list.includes(v as T);
const only = (s: Record<string, unknown>, keys: string[]) => Object.keys(s).every((k) => keys.includes(k));
const none = (s: Record<string, unknown>) => Object.keys(s).length === 0;
type PlainKind = "limits" | "holdings" | "income" | "tags" | "simulator" | "review" | "exposure" | "cash" | "bonds"
  | "savings" | "journal";
const card = <K extends PlainKind>(name: string, description: string, variants: readonly TileVariant[]): KindInfo<K> => ({
  name, description, variants, defaults: () => ({}) as TileSettings[K], valid: none as unknown as Check<K>,
});

export const KINDS: { [K in TileKind]: KindInfo<K> } = {
  summary: {
    name: "Wartość portfela", description: "Kwota, zmiana dziś i wybrane miary.", variants: ["S2", "M", "L"],
    defaults: () => ({ fields: ["total_gain", "twr_total", "invested", "income"] }),
    valid: ((s) => only(s, ["fields"]) && metricList(s.fields, MAX_SUMMARY_FIELDS)) as Check<"summary">,
  },
  metric: {
    name: "Jedna miara", description: "Jedna liczba, np. XIRR albo Sharpe.", variants: ["S1", "S2"],
    defaults: () => ({ metric: "xirr" }),
    valid: ((s) => only(s, ["metric"]) && isMetric(s.metric)) as Check<"metric">,
  },
  value_chart: {
    name: "Wykres wartości", description: "Wartość portfela w czasie.", variants: ["S2", "M4", "L4", "L6"],
    defaults: () => ({ range: "1R" }),
    valid: ((s) => only(s, ["range"]) && oneOf(VALUE_RANGES, s.range)) as Check<"value_chart">,
  },
  price_chart: {
    name: "Wykres ceny", description: "Cena jednego waloru z Twoimi zakupami i sprzedażami.", variants: ["S2", "M5", "L6"],
    defaults: () => ({ account_id: null, instrument_id: null, range: "buy" }),
    valid: ((s) => only(s, ["account_id", "instrument_id", "range"]) && isId(s.account_id ?? null)
      && isId(s.instrument_id ?? null) && oneOf(PRICE_RANGES, s.range)) as Check<"price_chart">,
  },
  allocation: {
    name: "Alokacja", description: "Podział portfela według typu, konta albo waluty.", variants: ["S2", "M4", "L4"],
    defaults: () => ({ by: "kind" }),
    valid: ((s) => only(s, ["by"]) && oneOf(ALLOCATION_BY, s.by)) as Check<"allocation">,
  },
  analysis: {
    name: "Analiza", description: "Wybrane miary za wybrany okres.", variants: ["S", "M", "L", "Lc"],
    defaults: () => ({ metrics: ["xirr", "max_drawdown"], period: "all" }),
    valid: ((s) => only(s, ["metrics", "period"]) && metricList(s.metrics, 6)
      && oneOf(ANALYSIS_PERIODS, s.period)) as Check<"analysis">,
  },
  limits: card("Limity IKE/IKZE", "Wpłaty w tym roku wobec limitu.", ["S2", "M2"]),
  movers: {
    name: "Dziś najbardziej", description: "Walory, które dziś najbardziej się zmieniły.", variants: ["S2", "M", "L"],
    defaults: () => ({ count: 5 }),
    valid: ((s) => only(s, ["count"]) && oneOf(ROW_COUNTS, s.count)) as Check<"movers">,
  },
  holdings: card("Walory", "Mapa cieplna walorów.", ["S3", "M3", "L5"]),
  income: card("Dochód i koszty", "Dochód pasywny i koszty.", ["S2", "M2"]),
  tags: card("Tagi", "Udział i zysk Twoich tagów.", ["S2", "M3"]),
  simulator: card("Symulator", "Ostatnie scenariusze „co by było, gdyby”.", ["S2", "M4"]),
  review: card("Przegląd AI", "Skrót ostatniego przeglądu portfela.", ["S2", "M4", "L4"]),
  exposure: card("Ekspozycja walutowa", "Udział walut w portfelu.", ["S2", "M3"]),
  operations: {
    name: "Ostatnie operacje", description: "Najnowsze operacje z Historii.", variants: ["S2", "M", "L"],
    defaults: () => ({ count: 5 }),
    valid: ((s) => only(s, ["count"]) && oneOf(ROW_COUNTS, s.count)) as Check<"operations">,
  },
  extremes: {
    name: "Najlepsze i najgorsze", description: "Walory z największym zyskiem i stratą za okres.", variants: ["S2", "M", "L"],
    defaults: () => ({ count: 3, period: "all" }),
    valid: ((s) => only(s, ["count", "period"]) && oneOf(EXTREME_COUNTS, s.count)
      && oneOf(HOLDINGS_PERIODS, s.period)) as Check<"extremes">,
  },
  cash: card("Gotówka na kontach", "Wolna gotówka razem i na każdym koncie.", ["S2", "M3"]),
  bonds: card("Obligacje", "Wartość obligacji i najbliższe wykupy.", ["S2", "M3"]),
  savings: card("Konta oszczędnościowe", "Saldo, oprocentowanie i odsetki.", ["S2", "M3"]),
  journal: card("Dziennik", "Ostatnie wpisy z dziennika.", ["S2", "M3"]),
};

export const KIND_ORDER = Object.keys(KINDS) as TileKind[];

/** A layout saved by plan 9 (S/M/L) reads as the nearest variant (the API does the same). */
const LEGACY_SIZES: Partial<Record<TileKind, Record<string, TileVariant>>> = {
  summary: { M: "M", L: "L" }, metric: { S: "S2" }, value_chart: { M: "M4", L: "L6" }, price_chart: { M: "M5", L: "L6" },
  allocation: { S: "S2", L: "L4" }, analysis: { M: "M", L: "Lc" }, limits: { M: "M2" }, movers: { M: "M", L: "L" },
  holdings: { M: "M3" }, income: { M: "M2" }, tags: { M: "M3" }, simulator: { M: "M4" }, review: { M: "M4" },
};

export const widthOf = (variant: TileVariant): TileWidth => variant[0] as TileWidth;
const rows = (n: number, perRow: number) => Math.ceil(n / perRow);

/** The height in U on a computer: the variant's digit, or a fixed part and one U for every row of chosen fields. */
export function heightOf(tile: Tile): number {
  const fixed = Number(tile.variant.slice(1));
  if (Number.isInteger(fixed) && fixed > 0) return fixed;
  const wide = widthOf(tile.variant) === "L";
  switch (tile.kind) {
    case "summary": return 2 + rows(tile.settings.fields.length, wide ? 4 : 2);
    case "analysis": {
      const n = tile.settings.metrics.length;
      if (tile.variant === "S") return 1 + Math.min(n, ANALYSIS_SMALL_METRICS);
      return (tile.variant === "Lc" ? 4 : 1) + rows(n, wide ? 4 : 2);
    }
    case "movers":
    case "operations": return 1 + rows(tile.settings.count, wide ? 4 : 2);
    case "extremes": return 1 + (wide ? rows(tile.settings.count, 2) : tile.settings.count);
    default: return 2;
  }
}

/** „M · 4U”: what the handle and the settings show. */
export function dimensionOf(tile: Tile): string {
  return `${widthOf(tile.variant)}${tile.variant === "Lc" ? " + wykres" : ""} · ${heightOf(tile)}U`;
}

function tile<K extends TileKind>(id: string, kind: K, variant: TileVariant, settings?: TileSettings[K]): Tile {
  return { id, kind, variant, settings: settings ?? KINDS[kind].defaults() } as Tile;
}

export const DEFAULT_LAYOUT: DashboardLayout = {
  version: 1,
  tiles: [
    // on a computer: 3U, 6U, then Alokacja 4U beside Analiza 2U over Limity 2U, then 3U — no gaps
    tile("summary", "summary", "L"),
    tile("value", "value_chart", "L6"),
    tile("allocation", "allocation", "M4"),
    tile("analysis", "analysis", "M"),
    tile("limits", "limits", "M2"),
    tile("movers", "movers", "L"),
  ],
};

/** A valid tile as this version stores it (a plan 9 `size` turned into its variant), or null. */
function validTile(raw: unknown, seen: Set<string>): Tile | null {
  if (typeof raw !== "object" || raw === null) return null;
  let t = raw as Record<string, unknown>;
  if (typeof t.id !== "string" || !/^[A-Za-z0-9_-]{1,20}$/.test(t.id) || seen.has(t.id)) return null;
  if (typeof t.kind !== "string" || !Object.hasOwn(KINDS, t.kind)) return null;
  const kind = t.kind as TileKind;
  if ("size" in t && !("variant" in t)) {
    const variant = LEGACY_SIZES[kind]?.[String(t.size)];
    if (variant === undefined) return null;
    const { size: _size, ...rest } = t;
    t = { ...rest, variant };
  }
  if (Object.keys(t).some((key) => !["id", "kind", "variant", "settings"].includes(key))) return null;
  const info = KINDS[kind] as KindInfo<TileKind>;
  if (!info.variants.includes(t.variant as TileVariant)) return null;
  const settings = t.settings;
  if (typeof settings !== "object" || settings === null || !info.valid(settings as Record<string, unknown>)) return null;
  return t as unknown as Tile;
}

/** The stored layout, without tiles this version cannot show; none stored (or another version) → the default. */
export function normalize(stored: unknown): DashboardLayout {
  if (typeof stored !== "object" || stored === null) return DEFAULT_LAYOUT;
  const { version, tiles } = stored as { version?: unknown; tiles?: unknown };
  if (version !== 1 || !Array.isArray(tiles)) return DEFAULT_LAYOUT;
  const seen = new Set<string>();
  const kept: Tile[] = [];
  for (const raw of tiles.slice(0, MAX_TILES)) {
    const valid = validTile(raw, seen);
    if (valid) {
      seen.add(valid.id);
      kept.push(valid);
    }
  }
  return { version: 1, tiles: kept };
}

export function newTileId(): string {
  return `t${Math.random().toString(36).slice(2, 10)}`;
}

/** A new tile of `kind` goes first, where it is seen; at the limit nothing is added. */
export function addTile(layout: DashboardLayout, kind: TileKind, variant?: TileVariant, id = newTileId()): DashboardLayout {
  if (layout.tiles.length >= MAX_TILES) return layout;
  const variants = KINDS[kind].variants;
  const chosen = variant !== undefined && variants.includes(variant) ? variant : variants[variants.length - 1]!;
  return { ...layout, tiles: [tile(id, kind, chosen), ...layout.tiles] };
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

export function updateTile(layout: DashboardLayout, id: string, patch: Partial<Pick<Tile, "variant" | "settings">>): DashboardLayout {
  return { ...layout, tiles: layout.tiles.map((t) => (t.id === id ? ({ ...t, ...patch } as Tile) : t)) };
}

export function sameLayout(a: DashboardLayout, b: DashboardLayout): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
