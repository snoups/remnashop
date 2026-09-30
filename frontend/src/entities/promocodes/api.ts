import { apiDelete, apiGet, apiPatch, apiPost } from "@shared/api/http";

// mirrors CreatePromocodeRequest.code on the backend
export const PROMOCODE_CODE_MAX_LENGTH = 64;
export const PROMOCODE_CODE_PATTERN = /^[A-Z0-9_-]+$/;

export type PromocodeRewardType =
  | "DURATION"
  | "TRAFFIC"
  | "DEVICES"
  | "SUBSCRIPTION"
  | "PERSONAL_DISCOUNT"
  | "PURCHASE_DISCOUNT";
export type PromocodeAvailability = "ALL" | "NEW" | "EXISTING" | "INVITED" | "ALLOWED";

export interface Promocode {
  id: number;
  code: string;
  is_active: boolean;
  reward_type: PromocodeRewardType;
  reward: number | null;
  reward_addon_id: number | null;
  reward_plan_id: number | null;
  reward_duration_days: number | null;
  availability: PromocodeAvailability;
  allowed_user_ids: number[];
  expires_at: string | null;
  max_activations: number | null;
  is_reusable: boolean;
  created_at: string | null;
}

export function listPromocodes(signal?: AbortSignal): Promise<Promocode[]> {
  return apiGet<Promocode[]>("/promocodes", signal);
}

export interface UserPromocodeActivation {
  activation_id: number;
  promocode_id: number;
  code: string;
  reward_type: PromocodeRewardType;
  reward: number | null;
  reward_duration_days: number | null;
  activated_at: string;
}

export function listUserPromocodeActivations(userId: number, signal?: AbortSignal): Promise<UserPromocodeActivation[]> {
  return apiGet<UserPromocodeActivation[]>(`/promocodes/activations?user_id=${userId}`, signal);
}

export interface CreatePromocodeRequest {
  code: string;
  reward_type: PromocodeRewardType;
  reward?: number | null;
  reward_addon_id?: number | null;
  reward_plan_id?: number | null;
  reward_duration_days?: number | null;
  availability: PromocodeAvailability;
  allowed_user_ids: number[];
  expires_at?: string | null;
  max_activations?: number | null;
  is_reusable: boolean;
}

export function createPromocode(payload: CreatePromocodeRequest): Promise<Promocode> {
  return apiPost<Promocode, CreatePromocodeRequest>("/promocodes", payload);
}

export interface UpdatePromocodeRequest {
  is_active?: boolean;
  availability?: PromocodeAvailability;
  allowed_user_ids?: number[];
  expires_at?: string | null;
  max_activations?: number | null;
  is_reusable?: boolean;
}

export function updatePromocode(promocodeId: number, payload: UpdatePromocodeRequest): Promise<Promocode> {
  return apiPatch<Promocode, UpdatePromocodeRequest>(`/promocodes/${promocodeId}`, payload);
}

export function deletePromocode(promocodeId: number): Promise<void> {
  return apiDelete<void>(`/promocodes/${promocodeId}`);
}

export function generatePromocodeCode(): Promise<string> {
  return apiPost<{ code: string }, Record<string, never>>("/promocodes/generate-code", {}).then(
    (result) => result.code,
  );
}

export interface PromocodeSummary {
  total_count: number;
  active_count: number;
  activations_count: number;
  activated_users_count: number;
  /** all-time, keyed by promocode id; compare against max_activations */
  activations_by_promocode: Record<string, number>;
  /** DURATION rewards plus SUBSCRIPTION durations */
  granted_days: number;
  granted_subscriptions_count: number;
  report_currency: string;
  /** paid orders' discounts from promocodes, in report_currency */
  discount_amount: string;
  discounted_orders_count: number;
}

export function getPromocodeSummary(signal?: AbortSignal): Promise<PromocodeSummary> {
  return apiGet<PromocodeSummary>("/promocodes/summary", signal);
}

export interface PromocodeActivatedUser {
  activation_id: number;
  user_id: number;
  name: string;
  subscription_id: number | null;
  activated_at: string;
}

export interface PromocodeActivatedUserPage {
  items: PromocodeActivatedUser[];
  total: number;
}

export function listPromocodeActivatedUsers(
  promocodeId: number,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<PromocodeActivatedUserPage> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return apiGet<PromocodeActivatedUserPage>(`/promocodes/${promocodeId}/users?${params.toString()}`, signal);
}
