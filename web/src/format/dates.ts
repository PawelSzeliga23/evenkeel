const MONTHS_GENITIVE = [
  "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
  "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
];
const MONTHS_SHORT = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
const MONTHS_NOMINATIVE = [
  "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
  "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
];
const WEEKDAYS = ["niedz.", "pon.", "wt.", "śr.", "czw.", "pt.", "sob."];

function parts(iso: string): { year: number; month: number; day: number } {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return { year: year!, month: month!, day: day! };
}

const pad = (n: number) => String(n).padStart(2, "0");

export function formatDate(iso: string): string {
  const { year, month, day } = parts(iso);
  return `${pad(day)}.${pad(month)}.${year}`;
}

export function formatDayLong(iso: string): string {
  const { year, month, day } = parts(iso);
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  return `${WEEKDAYS[weekday]}, ${day} ${MONTHS_GENITIVE[month - 1]}`;
}

export function monthShort(iso: string): string {
  return MONTHS_SHORT[parts(iso).month - 1]!;
}

/** "2026-10-03" → "październik 2026". */
export function monthLong(iso: string): string {
  const { year, month } = parts(iso);
  return `${MONTHS_NOMINATIVE[month - 1]} ${year}`;
}

/** "2026-03-02T09:30:00(+00:00)" → "02.03.2026, 09:30" — the time as the API wrote it. */
export function formatDateTime(iso: string): string {
  return `${formatDate(iso)}, ${iso.slice(11, 16)}`;
}

/** A moment from the API as "śr., 30 września, 14:32" in the browser's time zone. */
export function formatRefreshed(iso: string): string {
  const local = new Date(iso);
  return `${formatDayLong(todayIso(local))}, ${pad(local.getHours())}:${pad(local.getMinutes())}`;
}

export function formatDays(days: number): string {
  return days === 1 ? "1 dzień" : `${days} dni`;
}

export function todayIso(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function addMonths(iso: string, months: number): string {
  const { year, month, day } = parts(iso);
  const index = year * 12 + (month - 1) + months;
  const targetYear = Math.floor(index / 12);
  const targetMonth = (index % 12) + 1;
  const lastDay = new Date(Date.UTC(targetYear, targetMonth, 0)).getUTCDate();
  return `${targetYear}-${pad(targetMonth)}-${pad(Math.min(day, lastDay))}`;
}
