import { apiDelete, apiGet, apiPatch, apiPost } from "@shared/api/http";

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
}

export function listPromocodes(): Promise<Promocode[]> {
  return apiGet<Promocode[]>("/promocodes");
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
