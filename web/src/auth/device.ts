/** A session's device as „iPhone · Safari” from the browser's user-agent text (plan 8d). */
const SYSTEMS: [RegExp, string][] = [
  [/iPhone/, "iPhone"], [/iPad/, "iPad"], [/Android/, "Android"], [/Windows/, "Windows"],
  [/Macintosh|Mac OS X/, "Mac"], [/Linux/, "Linux"],
];
// Order matters: Edge and others also name Chrome, Chrome also names Safari.
const BROWSERS: [RegExp, string][] = [
  [/Edg\//, "Edge"], [/Firefox\/|FxiOS/, "Firefox"], [/Chrome\/|CriOS/, "Chrome"], [/Safari\//, "Safari"],
];

export function describeDevice(userAgent: string | null): string {
  if (!userAgent) return "Nieznane urządzenie";
  const system = SYSTEMS.find(([pattern]) => pattern.test(userAgent))?.[1];
  const browser = BROWSERS.find(([pattern]) => pattern.test(userAgent))?.[1];
  const parts = [system, browser].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "Przeglądarka";
}
