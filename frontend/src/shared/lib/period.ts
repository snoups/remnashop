export const DAY_MS = 86_400_000;

// "all time" has no previous window; trends then cover the last month
export const ALL_TIME_TREND_DAYS = 30;

/** Filters for a summary as it looked one period ago (ALL_TIME_TREND_DAYS back for "all time"). */
export function previousWindow(period: number, now = Date.now()): { createdFrom?: string; createdTo: string } {
  const shift = (period || ALL_TIME_TREND_DAYS) * DAY_MS;
  return {
    createdFrom: period ? new Date(now - 2 * shift).toISOString() : undefined,
    createdTo: new Date(now - shift).toISOString(),
  };
}
