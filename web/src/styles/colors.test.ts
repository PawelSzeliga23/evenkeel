import { describe, expect, it } from "vitest";

/** Every source file of the app, as text. */
const SOURCES = import.meta.glob("../**/*.{ts,tsx,css}", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

/** The two places a colour may be written (plan 8b), test files and test data. */
const ALLOWED = [/\.test\.tsx?$/, /\/test\//, /^\.\/(theme|chart-colors)\.css$/];
/** A line that has to carry a colour value that is data, not paint (e.g. the tag colours the API stores). */
const ALLOW_LINE = "colour-guard: allow";
const HEX = /(?<![\w&/])#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{3})(?![\w-])/i;
const RGB = /\brgba?\(/i;

describe("colours", () => {
  it("are written only in theme.css and chart-colors.css", () => {
    const offenders = Object.entries(SOURCES)
      .filter(([path]) => !ALLOWED.some((rule) => rule.test(path)))
      .flatMap(([path, text]) => text.split("\n").flatMap((line, i) =>
        !line.includes(ALLOW_LINE) && (HEX.test(line) || RGB.test(line)) ? [`${path}:${i + 1}: ${line.trim()}`] : []));
    expect(offenders).toEqual([]);
  });

  it("the guard sees the files", () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(50);
  });
});
