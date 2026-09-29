import { roundDigits } from "./decimal";

export const NBSP = " ";
export const MINUS = "−";

type Sign = "" | "+" | "−";

function group(whole: string): string {
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

function split(value: string, places: number): { negative: boolean; whole: string; fraction: string } {
  const { negative, digits } = roundDigits(value, places);
  const padded = digits.padStart(places + 1, "0");
  return { negative, whole: padded.slice(0, padded.length - places), fraction: padded.slice(padded.length - places) };
}

function signFor(negative: boolean, isZero: boolean, withPlus: boolean): Sign {
  if (negative) return MINUS;
  return withPlus && !isZero ? "+" : "";
}

export function moneyParts(value: string, { sign = false }: { sign?: boolean } = {}) {
  const { negative, whole, fraction } = split(value, 2);
  const isZero = !/[1-9]/.test(whole + fraction);
  return { sign: signFor(negative, isZero, sign), whole: group(whole), grosze: fraction };
}

export function formatMoney(
  value: string, { sign = false, currency = "zł" }: { sign?: boolean; currency?: string | null } = {},
): string {
  const parts = moneyParts(value, { sign });
  const amount = `${parts.sign}${parts.whole},${parts.grosze}`;
  return currency === null ? amount : `${amount}${NBSP}${currency}`;
}

/** Quantities and prices: up to `maxPlaces` decimals, trailing zeros dropped. */
export function formatDecimal(value: string, maxPlaces: number): string {
  const { negative, whole, fraction } = split(value, maxPlaces);
  const kept = fraction.replace(/0+$/, "");
  const isZero = !/[1-9]/.test(whole + kept);
  return `${negative && !isZero ? MINUS : ""}${group(whole)}${kept ? `,${kept}` : ""}`;
}

export function formatPercent(
  value: string | null, { sign = true, places = 2 }: { sign?: boolean; places?: number } = {},
): string {
  if (value === null) return "—";
  const { negative, whole, fraction } = split(value, places);
  const isZero = !/[1-9]/.test(whole + fraction);
  return `${signFor(negative, isZero, sign)}${group(whole)}${places ? `,${fraction}` : ""}${NBSP}%`;
}
