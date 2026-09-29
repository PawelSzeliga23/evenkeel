/** Exact money arithmetic on the API's decimal strings: grosze as BigInt, rounding half up on the digits. */

function increment(digits: string): string {
  const out = digits.split("");
  for (let i = out.length - 1; i >= 0; i--) {
    if (out[i] === "9") {
      out[i] = "0";
    } else {
      out[i] = String(Number(out[i]) + 1);
      return out.join("");
    }
  }
  return `1${out.join("")}`;
}

/** Splits "-1234.5678" into sign and digits rounded half up to `places` decimals: ["-", "123457"] for places=2. */
export function roundDigits(value: string, places: number): { negative: boolean; digits: string } {
  const text = value.trim();
  const negative = text.startsWith("-");
  const [whole = "0", fraction = ""] = text.replace(/^[-+]/, "").split(".");
  const padded = (fraction + "0".repeat(places + 1)).slice(0, places + 1);
  let digits = (whole || "0") + padded.slice(0, places);
  if (Number(padded[places]) >= 5) digits = increment(digits);
  digits = digits.replace(/^0+(?=\d)/, "");
  return { negative: negative && /[1-9]/.test(digits), digits };
}

export function toCents(value: string): bigint {
  const { negative, digits } = roundDigits(value, 2);
  const cents = BigInt(digits);
  return negative ? -cents : cents;
}

export function fromCents(cents: bigint): string {
  const negative = cents < 0n;
  const text = (negative ? -cents : cents).toString().padStart(3, "0");
  return `${negative ? "-" : ""}${text.slice(0, -2)}.${text.slice(-2)}`;
}

export function sumMoney(values: string[]): string {
  return fromCents(values.reduce((total, value) => total + toCents(value), 0n));
}

export function signOf(value: string | null): -1 | 0 | 1 {
  if (value === null) return 0;
  const cents = toCents(value);
  return cents > 0n ? 1 : cents < 0n ? -1 : 0;
}
