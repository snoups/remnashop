import type { TFunction } from "i18next";

import type { AnalyticsPeriod } from "@entities/analytics/api";
import { formatPercent } from "@shared/lib/format";
import { parseIsoDate } from "@shared/lib/iso-date";
import { DAY_MS } from "@shared/lib/period";
import type { KpiTrend } from "@shared/ui/KpiTile";

/** What a trend compares with: the period of the same length just before the selected one. */
export function previousPeriodHint(period: AnalyticsPeriod, t: TFunction): string {
  // "Year" is the last 365 days, not a calendar year
  if (period.kind === "days") return t("analytics.vsPreviousDays", { days: period.days });
  if (period.kind === "range") {
    const from = parseIsoDate(period.from);
    const to = parseIsoDate(period.to);
    if (from && to) return t("analytics.vsPreviousDays", { days: Math.round((to.getTime() - from.getTime()) / DAY_MS) + 1 });
  }
  return t("analytics.vsPrevious");
}

/** Change as a share of the previous value; none without a previous value to compare with. */
export function relativeTrend(
  current: number,
  previous: number,
  hint: string,
  language: string,
): KpiTrend | undefined {
  if (!(previous > 0)) return undefined;
  const delta = (current - previous) / previous;
  return { delta, text: formatPercent(Math.abs(delta), language), hint };
}

/** Change between two rates (0..1) in percentage points. */
export function ppTrend(current: number, previous: number, hint: string, t: TFunction, language: string): KpiTrend {
  const delta = current - previous;
  const value = new Intl.NumberFormat(language, { maximumFractionDigits: 1 }).format(Math.abs(delta * 100));
  return { delta, text: t("analytics.pp", { value }), hint };
}

export function countTrend(current: number, previous: number, hint: string, language: string): KpiTrend {
  const delta = current - previous;
  return {
    delta,
    text: Math.abs(delta).toLocaleString(language),
    hint,
  };
}
