import { apiGet } from "@shared/api/http";

export type OverviewPeriodDays = 0 | 7 | 30 | 90;

export type OverviewGranularity = "day" | "month";

export interface OverviewDailyCount {
  day: string;
  count: number;
}

export interface OverviewDailyAmount {
  day: string;
  amount: string;
}

export interface OverviewUsers {
  total: number;
  new_today: number;
  daily_registrations: OverviewDailyCount[];
}

export interface OverviewSubscriptions {
  total: number;
  active: number;
  limited: number;
  expired: number;
  disabled: number;
  expiring_soon: number;
}

export interface OverviewTransactions {
  paid_orders_count: number;
  revenue_by_currency: Record<string, string>;
  report_currency: string;
  daily_revenue: OverviewDailyAmount[];
}

export interface RuntimeProcess {
  process: string;
  pid: number;
  uptime_seconds: number;
  rss_bytes: number;
  event_loop_delay_ms: number;
  event_loop_p99_ms: number;
}

export interface HostMemory {
  total_bytes: number;
  used_bytes: number;
}

export interface OverviewOnline {
  current: number;
  daily_peak: OverviewDailyCount[];
}

export interface Overview {
  days: OverviewPeriodDays;
  granularity: OverviewGranularity;
  users: OverviewUsers | null;
  subscriptions: OverviewSubscriptions | null;
  transactions: OverviewTransactions | null;
  runtime: RuntimeProcess[];
  host_memory: HostMemory | null;
  online: OverviewOnline;
}

export function getOverview(days: OverviewPeriodDays, signal?: AbortSignal): Promise<Overview> {
  return apiGet<Overview>(`/overview?days=${days}`, signal);
}
