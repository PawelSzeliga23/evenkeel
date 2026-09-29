/** Polish plural: 1 pozycja, 2–4 pozycje (but 12–14 pozycji), 5+ pozycji. */
export function pluralPl(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one;
  const tens = n % 100;
  const units = n % 10;
  return units >= 2 && units <= 4 && (tens < 12 || tens > 14) ? few : many;
}
