import type { AddOnType } from "@entities/addons/api";
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@shared/api/http";
import { DAY_MS } from "@shared/lib/period";
import type { BadgeTone } from "@shared/ui/Badge";

export type SubscriptionStatus = "ACTIVE" | "LIMITED" | "EXPIRED" | "DISABLED" | "DELETED";
export type TrafficLimitStrategy = "NO_RESET" | "DAY" | "WEEK" | "MONTH" | "MONTH_ROLLING";

export interface PlanSnapshot {
  plan_id: number;
  public_code: string;
  name: string;
  price_paid: string;
  currency: string;
  duration_days: number;
  traffic_limit: number;
  device_limit: number;
  traffic_limit_strategy: TrafficLimitStrategy;
  is_trial: boolean;
  internal_squads: string[];
  external_squad: string | null;
  tag?: string | null;
  /** money and days behind the current credit, in the snapshot's currency; absent on an old snapshot */
  credit_paid?: string | null;
  credit_days?: number | null;
}

export interface AddOnEntitlement {
  addon_id: number | null;
  type: AddOnType;
  /** GB or devices on top of the subscription's own limit */
  amount: number;
  granted_at: string;
}

export interface SubscriptionListItem {
  id: number;
  user_id: number;
  remnawave_user_id: number;
  status: SubscriptionStatus;
  is_trial: boolean;
  tag: string | null;
  traffic_limit: number;
  device_limit: number;
  effective_traffic_limit: number;
  effective_device_limit: number;
  traffic_limit_strategy: TrafficLimitStrategy;
  internal_squads: string[];
  external_squad: string | null;
  expire_at: string;
  created_at: string | null;
  first_connected_at: string | null;
  /** the client's own last device removal, removal of all devices and link reissue */
  device_single_reset_at: string | null;
  device_all_reset_at: string | null;
  link_reset_at: string | null;
  url: string;
  plan_snapshot: PlanSnapshot;
  addon_entitlements: AddOnEntitlement[];
}

export function addonTotal(subscription: Pick<SubscriptionListItem, "addon_entitlements">, type: AddOnType): number {
  return subscription.addon_entitlements.reduce((sum, item) => sum + (item.type === type ? item.amount : 0), 0);
}

export interface SubscriptionRow extends SubscriptionListItem {
  /** null once the account is deleted */
  user_name: string | null;
}

export interface SubscriptionDetail extends SubscriptionListItem {
  /** from the panel; null when it is unreachable or hasn't seen the client */
  used_traffic: number | null; // bytes
  online_at: string | null;
  sub_last_opened_at: string | null;
  sub_last_user_agent: string | null;
}

export const SUBSCRIPTION_STATUS_BADGE_TONE: Record<SubscriptionStatus, BadgeTone> = {
  ACTIVE: "success",
  LIMITED: "warning",
  EXPIRED: "error",
  DISABLED: "neutral",
  DELETED: "neutral",
};

export const EXPIRING_SOON_DAYS = 7;

export function daysUntil(iso: string): number {
  return Math.ceil((new Date(iso).getTime() - Date.now()) / DAY_MS);
}

export function expiryToneClassName(days: number): string {
  if (days < 0) return "text-error";
  return days <= EXPIRING_SOON_DAYS ? "text-warning" : "text-muted-foreground";
}

export function formatTraffic(gb: number, unlimitedLabel: string): string {
  return gb === 0 ? unlimitedLabel : `${gb} GB`;
}

export function formatLimit(value: number, unlimitedLabel: string): string {
  return value === 0 ? unlimitedLabel : String(value);
}

export const DEFAULT_PAGE_SIZE = 50;

export interface SubscriptionListPage {
  items: SubscriptionRow[];
  total: number;
}

export interface SubscriptionListFilters {
  status?: SubscriptionStatus;
  search?: string;
  userId?: number;
  page?: number;
  pageSize?: number;
}

export function listSubscriptions(
  filters: SubscriptionListFilters = {},
  signal?: AbortSignal,
): Promise<SubscriptionListPage> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.search) params.set("search", filters.search);
  if (filters.userId !== undefined) params.set("user_id", String(filters.userId));
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<SubscriptionListPage>(`/subscriptions?${params.toString()}`, signal);
}

export interface UpdateSubscriptionRequest {
  tag?: string | null;
  traffic_limit?: number;
  device_limit?: number;
  traffic_limit_strategy?: TrafficLimitStrategy;
  expire_at?: string;
}

export function updateSubscription(
  subscriptionId: number,
  payload: UpdateSubscriptionRequest,
): Promise<SubscriptionListItem> {
  return apiPatch<SubscriptionListItem, UpdateSubscriptionRequest>(`/subscriptions/${subscriptionId}`, payload);
}

export interface SubscriptionSquads {
  internal_squads: string[];
  external_squad: string | null;
}

export function updateSubscriptionSquads(
  subscriptionId: number,
  squads: SubscriptionSquads,
): Promise<SubscriptionListItem> {
  return apiPut<SubscriptionListItem, SubscriptionSquads>(`/subscriptions/${subscriptionId}/squads`, squads);
}

export function getSubscription(subscriptionId: number, signal?: AbortSignal): Promise<SubscriptionDetail> {
  return apiGet<SubscriptionDetail>(`/subscriptions/${subscriptionId}`, signal);
}

export interface PanelSquad {
  uuid: string;
  name: string;
  kind: "internal" | "external";
}

export function listPanelSquads(signal?: AbortSignal): Promise<{ items: PanelSquad[]; total: number }> {
  return apiGet<{ items: PanelSquad[]; total: number }>("/subscriptions/squads", signal);
}

export function deleteSubscription(subscriptionId: number): Promise<void> {
  return apiDelete<void>(`/subscriptions/${subscriptionId}`);
}

export function deleteUserSubscriptions(userId: number): Promise<{ deleted: number }> {
  return apiPost<{ deleted: number }, Record<string, never>>(`/users/${userId}/subscriptions/bulk/delete`, {});
}

export interface GrantSubscriptionRequest {
  user_id: number;
  plan_id: number;
  duration_days: number;
}

export function grantSubscription(payload: GrantSubscriptionRequest): Promise<SubscriptionListItem> {
  return apiPost<SubscriptionListItem, GrantSubscriptionRequest>("/subscriptions", payload);
}

export interface ChangeSubscriptionPlanRequest {
  plan_id: number;
  /** null keeps the current expiry */
  duration_days: number | null;
}

export function changeSubscriptionPlan(
  subscriptionId: number,
  payload: ChangeSubscriptionPlanRequest,
): Promise<SubscriptionListItem> {
  return apiPost<SubscriptionListItem, ChangeSubscriptionPlanRequest>(
    `/subscriptions/${subscriptionId}/actions/change-plan`,
    payload,
  );
}

function subscriptionAction(subscriptionId: number, action: string): Promise<SubscriptionListItem> {
  return apiPost<SubscriptionListItem, Record<string, never>>(`/subscriptions/${subscriptionId}/actions/${action}`, {});
}

export const enableSubscription = (subscriptionId: number) => subscriptionAction(subscriptionId, "enable");
export const disableSubscription = (subscriptionId: number) => subscriptionAction(subscriptionId, "disable");
export const resetSubscriptionTraffic = (subscriptionId: number) => subscriptionAction(subscriptionId, "reset-traffic");
export const reissueSubscriptionLink = (subscriptionId: number) => subscriptionAction(subscriptionId, "reissue");

export interface SubscriptionDevice {
  hwid: string;
  platform: string | null;
  device_model: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface SubscriptionDeviceList {
  items: SubscriptionDevice[];
  total: number;
}

export function listSubscriptionDevices(subscriptionId: number, signal?: AbortSignal): Promise<SubscriptionDeviceList> {
  return apiGet<SubscriptionDeviceList>(`/subscriptions/${subscriptionId}/devices`, signal);
}

export function deleteSubscriptionDevice(subscriptionId: number, hwid: string): Promise<void> {
  return apiDelete<void>(`/subscriptions/${subscriptionId}/devices/${encodeURIComponent(hwid)}`);
}

export function deleteAllSubscriptionDevices(subscriptionId: number): Promise<SubscriptionListItem> {
  return apiPost<SubscriptionListItem, Record<string, never>>(`/subscriptions/${subscriptionId}/devices/bulk/delete`, {});
}

export type PanelSyncDirection = "FROM_PANEL" | "TO_PANEL";

export interface PanelSyncResult {
  direction: PanelSyncDirection;
  checked: number;
  updated: number;
  failed: number;
  missing: number;
  recreated: number;
  imported: number;
  deleted: number;
  over_limit: number;
  finished_at: string;
}

export interface PanelSyncDirectionStatus {
  direction: PanelSyncDirection;
  running: boolean;
  last: PanelSyncResult | null;
}

export interface PanelSyncStatus {
  from_panel: PanelSyncDirectionStatus;
  to_panel: PanelSyncDirectionStatus;
}

export interface PanelFieldDiff {
  field: string;
  shop: string;
  panel: string;
}

export interface MissingSquad {
  uuid: string;
  kind: "internal" | "external";
  /** how many of the checked subscriptions hold it */
  subscriptions: number;
}

/** a squad gone from the panel -> its replacement, null drops it */
export type SquadReplacements = Record<string, string | null>;

export interface SubscriptionPanelDiff {
  subscription_id: number;
  missing_in_panel: boolean;
  fields: PanelFieldDiff[];
  missing_squads: MissingSquad[];
}

export function listMissingPanelSquads(signal?: AbortSignal): Promise<{ items: MissingSquad[]; total: number }> {
  return apiGet<{ items: MissingSquad[]; total: number }>("/subscriptions/panel-sync/missing-squads", signal);
}

export interface SubscriptionListStats {
  paid_active: number;
  active_trials: number;
  /** paid, expiring within 7 days */
  expiring: number;
  /** of them within 24 hours */
  expiring_urgent: number;
  limited: number;
  disabled: number;
  /** paid, active or limited */
  paying: number;
  paying_never_connected: number;
}

export function getSubscriptionListStats(signal?: AbortSignal): Promise<SubscriptionListStats> {
  return apiGet<SubscriptionListStats>("/subscriptions/summary", signal);
}

export async function getPanelSyncStatus(signal?: AbortSignal): Promise<PanelSyncStatus> {
  return apiGet<PanelSyncStatus>("/subscriptions/panel-sync", signal);
}

/** each direction reads its own: pull adopt_unnamed and respect_subscription_limit, push recreate_missing and delete_orphans */
export type PanelSyncOptions = Record<
  "adopt_unnamed" | "respect_subscription_limit" | "recreate_missing" | "delete_orphans",
  boolean
>;

export async function startPanelSync(
  direction: PanelSyncDirection,
  options: PanelSyncOptions,
  squadReplacements: SquadReplacements = {},
): Promise<PanelSyncDirectionStatus> {
  const action = direction === "FROM_PANEL" ? "pull" : "push";
  return apiPost<PanelSyncDirectionStatus, PanelSyncOptions & { squad_replacements: SquadReplacements }>(
    `/subscriptions/panel-sync/actions/${action}`,
    { ...options, squad_replacements: squadReplacements },
  );
}

export async function getSubscriptionPanelDiff(
  subscriptionId: number,
  signal?: AbortSignal,
): Promise<SubscriptionPanelDiff> {
  return apiGet<SubscriptionPanelDiff>(`/subscriptions/${subscriptionId}/panel-diff`, signal);
}

export const pullSubscriptionFromPanel = (subscriptionId: number) =>
  subscriptionAction(subscriptionId, "pull-from-panel");
export const pushSubscriptionToPanel = (subscriptionId: number, squadReplacements: SquadReplacements = {}) =>
  apiPost<SubscriptionListItem, { squad_replacements: SquadReplacements }>(
    `/subscriptions/${subscriptionId}/actions/push-to-panel`,
    { squad_replacements: squadReplacements },
  );
