import { apiDelete, apiGet, apiPatch, apiPost } from "@shared/api/http";
import type { BadgeTone } from "@shared/ui/Badge";

export type SubscriptionStatus = "ACTIVE" | "LIMITED" | "EXPIRED" | "DISABLED" | "DELETED";
export type TrafficLimitStrategy = "NO_RESET" | "DAY" | "WEEK" | "MONTH" | "MONTH_ROLLING";

export interface PlanSnapshot {
  plan_id: number;
  name: string;
  price_paid: string;
  currency: string;
  duration_days: number;
  is_trial: boolean;
}

export interface SubscriptionListItem {
  id: number;
  user_id: number;
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
  url: string;
  plan_snapshot: PlanSnapshot;
}

export const SUBSCRIPTION_STATUS_BADGE_TONE: Record<SubscriptionStatus, BadgeTone> = {
  ACTIVE: "success",
  LIMITED: "warning",
  EXPIRED: "error",
  DISABLED: "neutral",
  DELETED: "neutral",
};

export const DEFAULT_PAGE_SIZE = 50;

export interface SubscriptionListPage {
  items: SubscriptionListItem[];
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

export function getSubscription(subscriptionId: number, signal?: AbortSignal): Promise<SubscriptionListItem> {
  return apiGet<SubscriptionListItem>(`/subscriptions/${subscriptionId}`, signal);
}

export function deleteSubscription(subscriptionId: number): Promise<void> {
  return apiDelete<void>(`/subscriptions/${subscriptionId}`);
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

export function deleteAllSubscriptionDevices(subscriptionId: number): Promise<void> {
  return apiPost<void, Record<string, never>>(`/subscriptions/${subscriptionId}/devices/bulk/delete`, {});
}
