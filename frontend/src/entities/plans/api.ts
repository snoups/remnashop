import { apiDelete, apiGet, apiPost, apiPut } from "@shared/api/http";

export type PlanType = "TRAFFIC" | "DEVICES" | "BOTH" | "UNLIMITED";
export type PlanAvailability = "ALL" | "NEW" | "EXISTING" | "INVITED" | "ALLOWED" | "LINK";
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
  durations: PlanDuration[];
}

export function listPlans(signal?: AbortSignal): Promise<Plan[]> {
  return apiGet<Plan[]>("/plans", signal);
}

export interface CreatePlanRequest {
  public_code: string;
  name: string;
  description?: string | null;
  tag?: string | null;
  type: PlanType;
  traffic_limit_strategy: TrafficLimitStrategy;
  traffic_limit: number;
  device_limit: number;
  is_trial: boolean;
}

export function createPlan(payload: CreatePlanRequest): Promise<Plan> {
  return apiPost<Plan, CreatePlanRequest>("/plans", payload);
}

export interface UpdatePlanRequest {
  name?: string;
  description?: string | null;
  tag?: string | null;
  type?: PlanType;
  traffic_limit_strategy?: TrafficLimitStrategy;
  traffic_limit?: number;
  device_limit?: number;
  is_active?: boolean;
  is_trial?: boolean;
}

export function updatePlan(planId: number, payload: UpdatePlanRequest): Promise<Plan> {
  return apiPut<Plan, UpdatePlanRequest>(`/plans/${planId}`, payload);
}

export function deletePlan(planId: number): Promise<void> {
  return apiDelete<void>(`/plans/${planId}`);
}

export function reorderPlans(planIds: number[]): Promise<Plan[]> {
  return apiPut<Plan[], { plan_ids: number[] }>("/plans/order", { plan_ids: planIds });
}

export interface SetPlanDurationsItem {
  days: number;
  order_index: number;
  base_price: string;
}

// The backend accepts (and ignores) an `overrides` field here -- per-currency
// price overrides live exclusively on the Pricing page's endpoints, this one
// only ever touches days/order/base_price. See admin_router.py's
// set_plan_durations, which rebuilds the usecase DTO without `overrides`.
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
