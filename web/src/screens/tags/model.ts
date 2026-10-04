import type { TagsReport } from "../../api/types";
import { tagColor } from "../../tags/model";
import type { ComparisonLine } from "../../charts/ComparisonChart";
import { pluralPl } from "../../format";

export const TAGS_PATH = "/analiza/tagi";
export const UNTAGGED = "untagged";
export const UNTAGGED_COLOR = "var(--untagged)";
export const NO_TAGS = "Nie masz jeszcze tagów. Dodasz je w szczegółach pozycji.";
export const NO_VALUE = "Żaden tag nie ma wartości na wybranych kontach.";

export const holdingsLabel = (n: number) => `${n} ${pluralPl(n, "walor", "walory", "walorów")}`;

export interface LegendEntry { key: string; label: string; color: string }

/** The legend of „Udział w czasie”: each tag of the report in its colour, then „bez tagu”. */
export function legend(report: TagsReport): LegendEntry[] {
  const names = new Map(report.tags.map((tag) => [String(tag.id), tag]));
  return report.history.series.flatMap((series) => {
    if (series.key === UNTAGGED) return [{ key: UNTAGGED, label: "bez tagu", color: UNTAGGED_COLOR }];
    const tag = names.get(series.key);
    return tag ? [{ key: series.key, label: tag.name, color: tagColor(tag.color) }] : [];
  });
}

/** The lines shown: every legend entry not hidden. */
export function chartLines(report: TagsReport, hidden: ReadonlySet<string>): ComparisonLine[] {
  const values = new Map(report.history.series.map((series) => [series.key, series.share_pct]));
  return legend(report).filter((entry) => !hidden.has(entry.key))
    .map((entry) => ({ ...entry, values: values.get(entry.key) ?? [] }));
}
