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
}

export interface OverviewSubscriptions {
  total: number;
  active: number;
  limited: number;
  expired: number;
  disabled: number;
  expiring_soon: number;
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

export interface Overview {
  users: OverviewUsers | null;
  subscriptions: OverviewSubscriptions | null;
  runtime: RuntimeProcess[];
  host_memory: HostMemory | null;
}

interface OverviewChart {
  days: OverviewPeriodDays;
  granularity: OverviewGranularity;
}

export interface RevenueChart extends OverviewChart {
  paid_orders_count: number;
  revenue_by_currency: Record<string, string>;
  report_currency: string;
  daily: OverviewDailyAmount[];
}

export interface RegistrationsChart extends OverviewChart {
  daily: OverviewDailyCount[];
}

export interface OnlineChart extends OverviewChart {
  current: number;
  daily_peak: OverviewDailyCount[];
}

export function getOverview(signal?: AbortSignal): Promise<Overview> {
  return apiGet<Overview>("/overview", signal);
}

export function getRevenueChart(days: OverviewPeriodDays, signal?: AbortSignal): Promise<RevenueChart> {
  return apiGet<RevenueChart>(`/overview/revenue?days=${days}`, signal);
}

export function getRegistrationsChart(days: OverviewPeriodDays, signal?: AbortSignal): Promise<RegistrationsChart> {
  return apiGet<RegistrationsChart>(`/overview/registrations?days=${days}`, signal);
}

export function getOnlineChart(days: OverviewPeriodDays, signal?: AbortSignal): Promise<OnlineChart> {
  return apiGet<OnlineChart>(`/overview/online?days=${days}`, signal);
}
