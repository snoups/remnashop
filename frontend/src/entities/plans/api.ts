import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";

export type PlanType = "TRAFFIC" | "DEVICES" | "BOTH" | "UNLIMITED";
export type PlanAvailability = "ALL" | "NEW" | "EXISTING" | "INVITED" | "ALLOWED" | "LINK";
export type PlanBadge = "POPULAR" | "BEST_VALUE";
export type TrafficLimitStrategy = "NO_RESET" | "DAY" | "WEEK" | "MONTH" | "MONTH_ROLLING";

export interface PlanPriceOverride {
  currency: string;
  price: string;
}

export interface PlanDuration {
  days: number;
  order_index: number;
  base_price: string;
  overrides: PlanPriceOverride[];
}

export interface Plan {
  id: number;
  public_code: string;
  name: string;
  description: string | null;
  tag: string | null;
  badge: PlanBadge | null;
  type: PlanType;
  availability: PlanAvailability;
  traffic_limit_strategy: TrafficLimitStrategy;
  traffic_limit: number;
  device_limit: number;
  allowed_telegram_ids: number[];
  allowed_emails: string[];
  internal_squads: string[];
  external_squad: string | null;
  order_index: number;
  is_active: boolean;
  is_trial: boolean;
  allow_bonus_days: boolean;
  allow_promocodes: boolean;
  discount_percent: number;
  discount_starts_at: string | null;
  discount_ends_at: string | null;
  durations: PlanDuration[];
}

export function getPlan(planId: number, signal?: AbortSignal): Promise<Plan> {
  return apiGet<Plan>(`/plans/${planId}`, signal);
}

export function listPlans(signal?: AbortSignal): Promise<Plan[]> {
  return apiGet<ListResponse<Plan>>("/plans", signal).then((response) => response.items);
}

export interface CreatePlanRequest {
  name: string;
  description?: string | null;
  tag?: string | null;
  badge?: PlanBadge | null;
  type: PlanType;
  traffic_limit_strategy: TrafficLimitStrategy;
  traffic_limit: number;
  device_limit: number;
  is_trial: boolean;
  allow_bonus_days: boolean;
  allow_promocodes: boolean;
}

export function createPlan(payload: CreatePlanRequest): Promise<Plan> {
  return apiPost<Plan, CreatePlanRequest>("/plans", payload);
}

export interface UpdatePlanRequest {
  name?: string;
  description?: string | null;
  tag?: string | null;
  badge?: PlanBadge | null;
  type?: PlanType;
  traffic_limit_strategy?: TrafficLimitStrategy;
  traffic_limit?: number;
  device_limit?: number;
  is_active?: boolean;
  is_trial?: boolean;
  allow_bonus_days?: boolean;
  allow_promocodes?: boolean;
}

export function updatePlan(planId: number, payload: UpdatePlanRequest): Promise<Plan> {
  return apiPatch<Plan, UpdatePlanRequest>(`/plans/${planId}`, payload);
}

export function deletePlan(planId: number): Promise<void> {
  return apiDelete<void>(`/plans/${planId}`);
}

export function reorderPlans(planIds: number[]): Promise<Plan[]> {
  return apiPost<ListResponse<Plan>, { plan_ids: number[] }>("/plans/actions/reorder", { plan_ids: planIds }).then(
    (response) => response.items,
  );
}

export interface SetPlanDurationsItem {
  days: number;
  order_index: number;
  base_price: string;
}

// per-currency overrides are set on the Pricing page; this endpoint ignores them
export function setPlanDurations(planId: number, durations: SetPlanDurationsItem[]): Promise<Plan> {
  return apiPut<Plan, { durations: SetPlanDurationsItem[] }>(`/plans/${planId}/durations`, { durations });
}

export interface UpdatePlanAccessRequest {
  availability: PlanAvailability;
  allowed_telegram_ids: number[];
  allowed_emails: string[];
}

export function updatePlanAccess(planId: number, payload: UpdatePlanAccessRequest): Promise<Plan> {
  return apiPut<Plan, UpdatePlanAccessRequest>(`/plans/${planId}/access`, payload);
}

export interface UpdatePlanDiscountRequest {
  discount_percent: number;
  discount_starts_at: string | null;
  discount_ends_at: string | null;
}

export function updatePlanDiscount(planId: number, payload: UpdatePlanDiscountRequest): Promise<Plan> {
  return apiPut<Plan, UpdatePlanDiscountRequest>(`/plans/${planId}/discount`, payload);
}

export interface PlanShareUrls {
  bot_url: string | null;
  webcabinet_url: string | null;
}

export function getPlanShareUrls(planId: number, signal?: AbortSignal): Promise<PlanShareUrls> {
  return apiGet<PlanShareUrls>(`/plans/${planId}/share`, signal);
}
