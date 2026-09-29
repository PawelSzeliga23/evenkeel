/** "SXR8.DE" → "SXR8": the exchange suffix does not fit the 40 px badge. */
export function shortTicker(ticker: string): string {
  return (ticker.split(".")[0] ?? ticker).slice(0, 5);
}
