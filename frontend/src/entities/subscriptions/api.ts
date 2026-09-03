import { apiDelete, apiGet, apiPut } from "@shared/api/http";

export type SubscriptionStatus = "ACTIVE" | "LIMITED" | "EXPIRED" | "DISABLED" | "DELETED";
export type TrafficLimitStrategy = "NO_RESET" | "DAY" | "WEEK" | "MONTH" | "MONTH_ROLLING";

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
}

export const DEFAULT_PAGE_SIZE = 50;

export interface SubscriptionListPage {
  items: SubscriptionListItem[];
  total: number;
}

export interface SubscriptionListFilters {
  status?: SubscriptionStatus;
  page?: number;
  pageSize?: number;
}

export function listSubscriptions(filters: SubscriptionListFilters = {}): Promise<SubscriptionListPage> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<SubscriptionListPage>(`/subscriptions?${params.toString()}`);
}

export interface UpdateSubscriptionRequest {
  tag?: string | null;
  traffic_limit?: number;
  device_limit?: number;
  traffic_limit_strategy?: TrafficLimitStrategy;
}

export function updateSubscription(
  subscriptionId: number,
  payload: UpdateSubscriptionRequest,
): Promise<SubscriptionListItem> {
  return apiPut<SubscriptionListItem, UpdateSubscriptionRequest>(`/subscriptions/${subscriptionId}`, payload);
}

export function deleteSubscription(subscriptionId: number): Promise<void> {
  return apiDelete<void>(`/subscriptions/${subscriptionId}`);
}
