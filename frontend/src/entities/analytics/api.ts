import { apiGet } from "@shared/api/http";

export type AnalyticsPeriodDays = 0 | 7 | 30 | 90;

export interface AnalyticsKpi {
  total_revenue_by_currency: Record<string, string>;
  report_currency: string;
  mrr: string;
  arpu: string;
  active_subscriptions: number;
  paid_orders_count: number;
  registered_in_period: number;
  paid_in_period: number;
  conversion_rate: number;
}

export interface ChurnSnapshot {
  window_days: number;
  prev_active: number;
  still_active: number;
  churned: number;
  churn_rate: number;
  retention_rate: number;
}

export interface Analytics {
  days: number;
  kpi: AnalyticsKpi;
  churn: ChurnSnapshot;
}

export function getAnalytics(days: AnalyticsPeriodDays, signal?: AbortSignal): Promise<Analytics> {
  return apiGet<Analytics>(`/analytics/overview?days=${days}`, signal);
}
