import type { TFunction } from "i18next";

import { formatPercent } from "@shared/lib/format";
import type { KpiTrend } from "@shared/ui/KpiTile";

/** Change as a share of the previous value; none without a previous value to compare with. */
export function relativeTrend(
  current: number,
  previous: number,
  previousText: string,
  t: TFunction,
  language: string,
): KpiTrend | undefined {
  if (!(previous > 0)) return undefined;
  const delta = (current - previous) / previous;
  return { delta, text: formatPercent(Math.abs(delta), language), hint: t("analytics.was", { value: previousText }) };
}

/** Change between two rates (0..1) in percentage points. */
export function ppTrend(current: number, previous: number, t: TFunction, language: string): KpiTrend {
  const delta = current - previous;
  const value = new Intl.NumberFormat(language, { maximumFractionDigits: 1 }).format(Math.abs(delta * 100));
  return { delta, text: t("analytics.pp", { value }), hint: t("analytics.was", { value: formatPercent(previous, language) }) };
}

export function countTrend(current: number, previous: number, t: TFunction, language: string): KpiTrend {
  const delta = current - previous;
  return {
    delta,
    text: Math.abs(delta).toLocaleString(language),
    hint: t("analytics.was", { value: previous.toLocaleString(language) }),
  };
}
