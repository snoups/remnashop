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

export interface FunnelStep {
  key: string;
  count: number;
  pct_of_start: number;
  pct_of_prev: number;
}

export interface Funnel {
  days: number;
  steps: FunnelStep[];
}

export function getFunnel(days: AnalyticsPeriodDays, signal?: AbortSignal): Promise<Funnel> {
  return apiGet<Funnel>(`/analytics/funnel?days=${days}`, signal);
}

export interface CohortRow {
  cohort: string;
  cohort_size: number;
  retention_by_month: number[];
}

export interface Cohorts {
  cohorts: CohortRow[];
}

export function getCohorts(signal?: AbortSignal): Promise<Cohorts> {
  return apiGet<Cohorts>("/analytics/cohorts", signal);
}

export interface LtvBucket {
  label: string;
  lower_bound: string;
  upper_bound: string | null;
  users: number;
}

export interface LtvDistribution {
  report_currency: string;
  buckets: LtvBucket[];
}

export function getLtvDistribution(signal?: AbortSignal): Promise<LtvDistribution> {
  return apiGet<LtvDistribution>("/analytics/ltv-distribution", signal);
}
