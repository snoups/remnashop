import { apiGet } from "@shared/api/http";

export type AnalyticsPeriodDays = 0 | 7 | 30 | 90;

export interface AnalyticsPeriodInfo {
  start: string;
  end: string;
  previous_start: string;
  previous_end: string;
}

export interface PeriodKpi {
  revenue: string;
  payments: number;
  paying_users: number;
  arppu: string;
  new_payers: number;
  conversion_cohort: number;
  converted: number;
  conversion_rate: number;
  churn_base: number;
  churned: number;
  churn_rate: number;
}

export interface SnapshotKpi {
  mrr: string;
  paid_subscriptions: number;
  limited_subscriptions: number;
  active_trials: number;
}

export interface Analytics {
  period: AnalyticsPeriodInfo;
  report_currency: string;
  revenue_by_currency: Record<string, string>;
  conversion_window_days: number;
  current: PeriodKpi;
  previous: PeriodKpi;
  snapshot: SnapshotKpi;
}

export function periodParams(days: AnalyticsPeriodDays): URLSearchParams {
  const today = new Date();
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const params = new URLSearchParams({ period_to: iso(today) });
  if (days !== 0) {
    const from = new Date(today);
    from.setUTCDate(from.getUTCDate() - (days - 1));
    params.set("period_from", iso(from));
  }
  return params;
}

export function getAnalytics(days: AnalyticsPeriodDays, signal?: AbortSignal): Promise<Analytics> {
  return apiGet<Analytics>(`/analytics/overview?${periodParams(days).toString()}`, signal);
}

export interface FunnelStep {
  key: string;
  count: number;
  pct_of_start: number;
  pct_of_prev: number;
}

export interface FunnelSourceRow {
  source: "organic" | "ad_link" | "referral";
  ad_link_id: number | null;
  name: string | null;
  registered: number;
  connected: number;
  paid: number;
  repeat_paid: number;
}

export interface Funnel {
  period: AnalyticsPeriodInfo;
  steps: FunnelStep[];
  paid_via_trial: number;
  by_source: FunnelSourceRow[];
}

export function getFunnel(days: AnalyticsPeriodDays, signal?: AbortSignal): Promise<Funnel> {
  return apiGet<Funnel>(`/analytics/funnel?${periodParams(days).toString()}`, signal);
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
  payers: number;
  mean: string;
  median: string;
}

export interface LtvGroup {
  key: string;
  source: "organic" | "ad_link" | "referral" | null;
  customers: number;
  avg_ltv: string;
}

export interface TopPayer {
  user_id: number;
  name: string;
  username: string | null;
  current_plan: string | null;
  payments: number;
  spent: string;
  last_paid_at: string;
}

export interface LtvBreakdown {
  report_currency: string;
  by_first_plan: LtvGroup[];
  by_source: LtvGroup[];
  top_payers: TopPayer[];
}

export function getLtvDistribution(signal?: AbortSignal): Promise<LtvDistribution> {
  return apiGet<LtvDistribution>("/analytics/ltv-distribution", signal);
}
