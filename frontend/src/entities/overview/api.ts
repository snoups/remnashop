import type { ListResponse } from "@shared/api/http";
import type { PurchaseType } from "@entities/transactions/api";
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
  count: number;
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
  paid_active: number;
  trials: number;
}

/** Every field but `process` is null while the process sends no heartbeat. */
export interface RuntimeProcess {
  process: string;
  instance: string | null;
  pid: number | null;
  uptime_seconds: number | null;
  rss_bytes: number | null;
  event_loop_delay_ms: number | null;
  event_loop_p99_ms: number | null;
}

export interface HostMemory {
  total_bytes: number;
  used_bytes: number;
}

export interface HostStats {
  cpu_percent: number | null;
  cpu_count: number;
  load_1: number | null;
  load_5: number | null;
  load_15: number | null;
  disk_total_bytes: number | null;
  disk_used_bytes: number | null;
}

export interface RevenueToday {
  report_currency: string;
  today: string;
  yesterday_same_time: string;
  /** fraction, null without a comparable yesterday */
  change: number | null;
}

export interface RecentPayment {
  user_id: number;
  name: string;
  plan_name: string;
  gateway_type: string;
  purchase_type: PurchaseType;
  amount: string;
  currency: string;
  paid_at: string;
}

export interface Overview {
  users: OverviewUsers | null;
  subscriptions: OverviewSubscriptions | null;
  runtime: RuntimeProcess[];
  host_memory: HostMemory | null;
  host: HostStats | null;
  revenue_today: RevenueToday | null;
  recent_payments: RecentPayment[] | null;
}

interface OverviewChart {
  days: OverviewPeriodDays;
  granularity: OverviewGranularity;
}

export interface RevenueChart extends OverviewChart {
  paid_orders_count: number;
  report_currency: string;
  daily: OverviewDailyAmount[];
}

export interface OnlineChart extends OverviewChart {
  current: number;
  daily_peak: OverviewDailyCount[];
}

export interface HourlyOnline {
  current: number;
  points: { hour: string; peak: number | null }[];
}

export interface NodeCard {
  name: string;
  country_code: string;
  is_connected: boolean;
  is_disabled: boolean;
  users_online: number;
  traffic_used_bytes: number | null;
  last_status_change: string | null;
}

export interface CountryCard {
  country_code: string;
  nodes: number;
  connected: number;
  users_online: number;
}

export interface NodesOverview {
  available: boolean;
  nodes: NodeCard[];
  countries: CountryCard[];
}

export interface ClientApps {
  available: boolean;
  total_devices: number;
  average_per_user: number;
  platforms: { platform: string; total: number; apps: { app: string; count: number }[] }[];
}

export type AttentionKind =
  | "process_down"
  | "outbox_stuck"
  | "panel_unavailable"
  | "node_offline"
  | "gateway_failures"
  | "smtp_failed"
  | "backup_failed"
  | "backup_overdue"
  | "broadcast_failed"
  | "paid_not_fulfilled"
  | "stale_pending"
  | "broadcast_stalled"
  | "email_undeliverable"
  | "expiring_paid"
  | "api_token_expiring"
  | "bot_webhook"
  | "unrated_anchor_amounts";

export interface AttentionItem {
  kind: AttentionKind;
  severity: "critical" | "warning";
  count: number;
  subject: string | null;
  since: string | null;
}

export function getOverview(signal?: AbortSignal): Promise<Overview> {
  return apiGet<Overview>("/overview", signal);
}

export function getRevenueChart(days: OverviewPeriodDays, signal?: AbortSignal): Promise<RevenueChart> {
  return apiGet<RevenueChart>(`/overview/revenue?days=${days}`, signal);
}

export function getOnlineChart(days: OverviewPeriodDays, signal?: AbortSignal): Promise<OnlineChart> {
  return apiGet<OnlineChart>(`/overview/online?days=${days}`, signal);
}

export function getHourlyOnline(signal?: AbortSignal): Promise<HourlyOnline> {
  return apiGet<HourlyOnline>("/overview/online/hourly", signal);
}

export function getNodesOverview(signal?: AbortSignal): Promise<NodesOverview> {
  return apiGet<NodesOverview>("/overview/nodes", signal);
}

export function getClientApps(signal?: AbortSignal): Promise<ClientApps> {
  return apiGet<ClientApps>("/overview/client-apps", signal);
}

export interface Recap {
  report_currency: string;
  revenue_total: string;
  customers: number;
  payers: number;
  active_subscriptions: number;
  transactions: number;
  month_revenue: string;
  new_customers: number;
  new_payers: number;
  /** null: the panel didn't answer */
  nodes: number | null;
  countries: number | null;
  since: string;
}

export function getRecap(signal?: AbortSignal): Promise<Recap> {
  return apiGet<Recap>("/overview/recap", signal);
}

export function getAttention(signal?: AbortSignal): Promise<ListResponse<AttentionItem>> {
  return apiGet<ListResponse<AttentionItem>>("/overview/attention", signal);
}
