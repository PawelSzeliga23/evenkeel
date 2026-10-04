/** Wykres ceny (plan 7e): ranges and the names of the operation markers. */
import type { IsoDate, Money, PriceChartData, PriceMarker, PriceNote } from "../../api/types";
import { NBSP, addMonths, formatDate, formatDecimal, formatMoney } from "../../format";

export type PriceRange = "buy" | "6m" | "1y" | "5y" | "max";

export const PRICE_RANGES: { value: PriceRange; label: string }[] = [
  { value: "buy", label: "Od zakupu" },
  { value: "6m", label: "6M" },
  { value: "1y", label: "1R" },
  { value: "5y", label: "5L" },
  { value: "max", label: "Maks" },
];

const DAYS_BEFORE_BUY = 14;
const MONTHS: Record<Exclude<PriceRange, "buy" | "max">, number> = { "6m": 6, "1y": 12, "5y": 60 };
const SYMBOLS: Record<string, string> = { EUR: "€", USD: "$", PLN: "zł" };

function addDays(iso: IsoDate, days: number): IsoDate {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year!, month! - 1, day! + days)).toISOString().slice(0, 10);
}

/** The first day of the range (ISO), null for Maks. „Od zakupu” without a purchase is a year. */
export function rangeFrom(range: PriceRange, firstBuy: IsoDate | null, today: IsoDate): IsoDate | null {
  if (range === "max") return null;
  if (range === "buy") return firstBuy ? addDays(firstBuy, -DAYS_BEFORE_BUY) : addMonths(today, -12);
  return addMonths(today, -MONTHS[range]);
}

export function currencySymbol(currency: string | null): string {
  return currency === null ? "" : (SYMBOLS[currency] ?? currency);
}

/** A price as XTB writes it: at least two places, up to four. */
export function formatPrice(value: Money, currency: string | null): string {
  const [whole, fraction = ""] = formatDecimal(value, 4).split(",");
  const symbol = currencySymbol(currency);
  return `${whole},${fraction.padEnd(2, "0")}${symbol ? `${NBSP}${symbol}` : ""}`;
}

/** A day of journal entries on the chart (plan 7f-2): drawn as „N” above the price. */
export interface NoteMark { date: IsoDate; kind: "note"; price: null; entries: PriceNote["entries"] }
export type ChartMark = PriceMarker | NoteMark;

/** The operations, then one mark per day of entries; the chart's and the panel's index into this list. */
export function chartMarks(data: PriceChartData): ChartMark[] {
  return [...data.markers, ...data.notes.map((n): NoteMark => ({ date: n.date, kind: "note", price: null, entries: n.entries }))];
}

export function markerLabel(marker: ChartMark, currency: string | null): string {
  const day = formatDate(marker.date);
  if (marker.kind === "note") return `Notatka ${day}`;
  if (marker.kind === "dividend") {
    const amount = marker.amount_pln === null ? "kwota po pobraniu kursu NBP" : formatMoney(marker.amount_pln, { sign: true });
    return `Dywidenda ${day}, ${amount}`;
  }
  const kind = marker.kind === "buy" ? "Zakup" : "Sprzedaż";
  const quantity = marker.quantity === null ? "" : `${formatDecimal(marker.quantity, 8)} szt.`;
  const price = marker.price === null ? "" : `po ${formatPrice(marker.price, currency)}`;
  return `${kind} ${day}, ${[quantity, price].filter(Boolean).join(" ")}`;
}
