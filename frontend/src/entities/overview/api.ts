import { apiGet } from "@shared/api/http";

export type OverviewPeriodDays = 7 | 30 | 90;

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
  active: number;
}

export interface OverviewPayments {
  paid_orders_count: number;
  revenue_by_currency: Record<string, string>;
  report_currency: string;
  daily_revenue: OverviewDailyAmount[];
}

export interface Overview {
  days: OverviewPeriodDays;
  users: OverviewUsers | null;
  subscriptions: OverviewSubscriptions | null;
  payments: OverviewPayments | null;
}

export function getOverview(days: OverviewPeriodDays, signal?: AbortSignal): Promise<Overview> {
  return apiGet<Overview>(`/overview?days=${days}`, signal);
}
