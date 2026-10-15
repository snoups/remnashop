import { apiGet } from "@shared/api/http";
import { toIsoDate } from "@shared/lib/iso-date";
import type { Permission } from "@shared/types/rbac";
import type { PromocodeRewardType } from "@entities/promocodes/api";

export type AnalyticsPeriod =
  | { kind: "days"; days: 7 | 30 | 90 | 365 }
  | { kind: "all" }
  | { kind: "range"; from: string; to: string };

/** one per analytics tab, in tab order */
export const ANALYTICS_TAB_PERMISSIONS = {
  metrics: "ANALYTICS_VIEW",
  revenue: "ANALYTICS_REVENUE_VIEW",
  funnel: "ANALYTICS_FUNNEL_VIEW",
  trial: "ANALYTICS_TRIAL_VIEW",
  retention: "ANALYTICS_RETENTION_VIEW",
  ltv: "ANALYTICS_LTV_VIEW",
  sources: "ANALYTICS_SOURCES_VIEW",
  promocodes: "ANALYTICS_PROMOCODES_VIEW",
} as const satisfies Record<string, Permission>;

export type SourceKind = "organic" | "ad_link" | "referral";
export type RevenueGranularity = "day" | "week" | "month";

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


export function periodParams(period: AnalyticsPeriod, today = new Date()): URLSearchParams {
  if (period.kind === "range") return new URLSearchParams({ period_from: period.from, period_to: period.to });
  const params = new URLSearchParams({ period_to: toIsoDate(today) });
  if (period.kind === "days") {
    const from = new Date(today.getFullYear(), today.getMonth(), today.getDate() - (period.days - 1));
    params.set("period_from", toIsoDate(from));
  }
  return params;
}

export function getAnalytics(period: AnalyticsPeriod, signal?: AbortSignal): Promise<Analytics> {
  return apiGet<Analytics>(`/analytics/overview?${periodParams(period).toString()}`, signal);
}

export interface FunnelStep {
  key: string;
  count: number;
  pct_of_start: number;
  pct_of_prev: number;
}

export interface FunnelSourceRow {
  source: SourceKind;
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

export function getFunnel(period: AnalyticsPeriod, signal?: AbortSignal): Promise<Funnel> {
  return apiGet<Funnel>(`/analytics/funnel?${periodParams(period).toString()}`, signal);
}

export interface CohortRow {
  cohort: string;
  cohort_size: number;
  retention_by_month: number[];
}

export interface Cohorts {
  items: CohortRow[];
  total: number;
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
  source: SourceKind | null;
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

export function getLtvBreakdown(signal?: AbortSignal): Promise<LtvBreakdown> {
  return apiGet<LtvBreakdown>("/analytics/ltv-breakdown", signal);
}

export interface RevenueTotals {
  revenue: string;
  payments: number;
  avg_check: string;
  median_check: string;
  refunds: number;
  refunded: string;
  previous_revenue: string;
  previous_payments: number;
}

export interface RevenueBucket {
  start: string;
  new: string;
  renew: string;
  change: string;
  previous_total: string;
}

export interface RevenueGroup {
  key: string;
  payments: number;
  revenue: string;
}

export interface GatewayStats {
  gateway_type: string;
  paid: number;
  canceled: number;
  failed: number;
  refunded: number;
  revenue: string;
}

export interface Revenue {
  period: AnalyticsPeriodInfo;
  report_currency: string;
  granularity: RevenueGranularity;
  totals: RevenueTotals;
  series: RevenueBucket[];
  by_plan: RevenueGroup[];
  by_duration: RevenueGroup[];
  gateways: GatewayStats[];
}

export function getRevenue(
  period: AnalyticsPeriod,
  granularity: RevenueGranularity,
  signal?: AbortSignal,
): Promise<Revenue> {
  const params = periodParams(period);
  params.set("granularity", granularity);
  return apiGet<Revenue>(`/analytics/revenue?${params.toString()}`, signal);
}

export interface TrialDayBucket {
  key: string;
  count: number;
}

export interface TimeToPayBucket {
  key: string;
  via_trial: number;
  direct: number;
}

export interface Trial {
  period: AnalyticsPeriodInfo;
  report_currency: string;
  trials: number;
  converted: number;
  conversion_rate: number;
  previous_conversion_rate: number;
  revenue_from_converted: string;
  median_days_to_pay: number;
  trial_days: number;
  by_trial_day: TrialDayBucket[];
  time_to_first_payment: TimeToPayBucket[];
  plans_after_trial: RevenueGroup[];
}

export function getTrial(period: AnalyticsPeriod, signal?: AbortSignal): Promise<Trial> {
  return apiGet<Trial>(`/analytics/trial?${periodParams(period).toString()}`, signal);
}

export interface RetentionPoint {
  months: number;
  rate: number;
  eligible: number;
}

export interface ExpiringWeek {
  key: string;
  count: number;
  mrr_at_risk: string;
}

export interface ExpiringCustomer {
  user_id: number;
  name: string;
  username: string | null;
  plan_name: string;
  expire_at: string;
  spent: string;
  renewals: number;
}

export interface PlanActive {
  plan_name: string;
  active: number;
  limited: number;
}

export interface MonthlyChurn {
  month: string;
  base: number;
  churned: number;
  rate: number;
}

export interface Retention {
  report_currency: string;
  points: RetentionPoint[];
  avg_paid_months: number;
  expiring_paid: number;
  expiring_trials: number;
  expiring_weeks: ExpiringWeek[];
  expiring_top: ExpiringCustomer[];
  active_by_plan: PlanActive[];
  monthly_churn: MonthlyChurn[];
}

export function getRetention(signal?: AbortSignal): Promise<Retention> {
  return apiGet<Retention>("/analytics/retention", signal);
}

export interface SourceRow {
  source: SourceKind;
  ad_link_id: number | null;
  name: string | null;
  registrations: number;
  payers: number;
  conversion_rate: number;
  revenue: string;
  revenue_per_payer: string;
}

export interface ReferralPayback {
  referred_revenue: string;
  reward_days: number;
  reward_points: number;
  referrers: number;
  deep_levels_revenue_share: number;
}

export interface TopReferrer {
  user_id: number;
  name: string;
  invited: number;
  paid: number;
  revenue: string;
  reward_days: number;
}

export interface Sources {
  period: AnalyticsPeriodInfo;
  report_currency: string;
  channels: SourceRow[];
  ad_links: SourceRow[];
  referral: ReferralPayback;
  top_referrers: TopReferrer[];
}

export function getSources(period: AnalyticsPeriod, signal?: AbortSignal): Promise<Sources> {
  return apiGet<Sources>(`/analytics/sources?${periodParams(period).toString()}`, signal);
}

export interface RewardTypeCount {
  reward_type: PromocodeRewardType;
  activations: number;
}

export interface PromocodeRow {
  promocode_id: number;
  code: string;
  reward_type: PromocodeRewardType;
  reward: number | null;
  reward_duration_days: number | null;
  activations: number;
  total_activations: number;
  max_activations: number | null;
  revenue_after: string;
  conversion_rate: number | null;
  status: "ACTIVE" | "EXPIRED" | "INACTIVE";
}

export interface PromocodeStats {
  period: AnalyticsPeriodInfo;
  report_currency: string;
  activations: number;
  codes_used: number;
  discount_given: string;
  revenue_with_discount: string;
  revenue_share: number;
  free_reward_conversion: number;
  by_reward_type: RewardTypeCount[];
  codes: PromocodeRow[];
}

export function getPromocodeStats(period: AnalyticsPeriod, signal?: AbortSignal): Promise<PromocodeStats> {
  return apiGet<PromocodeStats>(`/analytics/promocodes?${periodParams(period).toString()}`, signal);
}
