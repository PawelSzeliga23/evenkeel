/** What a person types into an amount field, read into the API's decimal text — never through a float. */
export function parseAmount(text: string, places = 2): string | null {
  const cleaned = text.replace(/[\s ]/g, "").replace(",", ".");
  if (!new RegExp(`^\\d+(\\.\\d{1,${places}})?$`).test(cleaned)) return null;
  const [whole = "0", fraction] = cleaned.split(".");
  return `${whole.replace(/^0+(?=\d)/, "")}${fraction ? `.${fraction}` : ""}`;
}

export function isPositive(decimal: string): boolean {
  return /[1-9]/.test(decimal);
}
