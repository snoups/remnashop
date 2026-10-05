import type { OverviewPeriodDays } from "@entities/overview/api";
import { parseIsoDate } from "@shared/lib/iso-date";
import { useAsyncResource, type AsyncState } from "@shared/lib/use-async-resource";

// each chart card owns its period: refetches on its own pill switch or a global refresh
export function useChart<T>(
  fetchChart: (days: OverviewPeriodDays, signal: AbortSignal) => Promise<T>,
  days: OverviewPeriodDays,
  refreshKey: number,
): AsyncState<T> {
  const [state] = useAsyncResource((signal) => fetchChart(days, signal), {
    deps: [fetchChart, days, refreshKey],
    keepData: true,
  });
  return state;
}

export function fillDailySeries<T extends { day: string }>(
  sparse: T[],
  days: number,
  emptyValue: (day: string) => T,
): T[] {
  const byDay = new Map(sparse.map((item) => [item.day, item]));
  const result: T[] = [];
  const today = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setUTCDate(d.getUTCDate() - i);
    const key = d.toISOString().slice(0, 10);
    result.push(byDay.get(key) ?? emptyValue(key));
  }
  return result;
}

export function formatChartDay(iso: string, language: string): string {
  return parseIsoDate(iso)?.toLocaleDateString(language, { day: "2-digit", month: "2-digit" }) ?? iso;
}

// theme tokens, not hex: --color-primary follows the dashboard's appearance settings
export const CHART_TICK = { fill: "var(--color-muted-foreground)", fontSize: 11 };
export const CHART_TOOLTIP_STYLE = {
  contentStyle: { background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: 12 },
  labelStyle: { color: "var(--color-foreground)" },
  itemStyle: { color: "var(--color-foreground)" },
};
