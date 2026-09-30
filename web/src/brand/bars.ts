/** The splash's endless rising chart. Values are relative to the newest bar (always 1); each bar is higher than
 * the one before it. */
export interface SplashBar { id: number; value: number; leaving: boolean }

export const VISIBLE_BARS = 4;
const step = (random: () => number) => 1.12 + random() * 0.33;
let lastId = 0;

export function firstBars(random: () => number = Math.random): SplashBar[] {
  const values = [1];
  while (values.length < VISIBLE_BARS) values.unshift(values[0]! / step(random));
  return values.map((value) => ({ id: ++lastId, value, leaving: false }));
}

/** The oldest visible bar starts leaving and a higher one arrives; everything is rescaled so the newest is 1 again,
 * which keeps the values from growing without bound. */
export function nextBars(bars: readonly SplashBar[], random: () => number = Math.random): SplashBar[] {
  const oldest = bars.find((bar) => !bar.leaving)?.id;
  const scale = 1 / step(random);
  const kept = bars.map((bar) => ({ ...bar, value: bar.value * scale, leaving: bar.leaving || bar.id === oldest }));
  return [...kept, { id: ++lastId, value: 1, leaving: false }];
}
