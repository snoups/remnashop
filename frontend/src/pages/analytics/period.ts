import type { TFunction } from "i18next";
import { useOutletContext } from "react-router-dom";

import type { AnalyticsPeriod } from "@entities/analytics/api";
import { parseIsoDate } from "@shared/lib/iso-date";

export interface AnalyticsOutletContext {
  period: AnalyticsPeriod;
  setPeriod: (period: AnalyticsPeriod) => void;
}

export function useAnalyticsPeriod(): AnalyticsOutletContext {
  return useOutletContext<AnalyticsOutletContext>();
}

function formatDateRange(from: Date, to: Date, language: string): string {
  const withYear = from.getFullYear() !== to.getFullYear() || from.getFullYear() !== new Date().getFullYear();
  return new Intl.DateTimeFormat(language, {
    day: "numeric",
    month: "short",
    ...(withYear ? { year: "numeric" } : {}),
  }).formatRange(from, to);
}

export function periodLabel(period: AnalyticsPeriod, t: TFunction, language: string): string {
  if (period.kind === "all") return t("dashboard.periodAll");
  if (period.kind === "days") {
    return period.days === 365 ? t("analytics.period.year") : t("dashboard.periodDays", { count: period.days });
  }
  const from = parseIsoDate(period.from);
  const to = parseIsoDate(period.to);
  return from && to ? formatDateRange(from, to, language) : "";
}

/** Backend period bounds (dates or datetimes, end exclusive) → "2–31 Aug". */
export function rangeLabel(fromIso: string, toExclusiveIso: string, language: string): string {
  const from = parseIsoDate(fromIso.slice(0, 10));
  const toExclusive = parseIsoDate(toExclusiveIso.slice(0, 10));
  if (!from || !toExclusive) return "";
  const to = new Date(toExclusive.getFullYear(), toExclusive.getMonth(), toExclusive.getDate() - 1);
  return formatDateRange(from, to < from ? from : to, language);
}
