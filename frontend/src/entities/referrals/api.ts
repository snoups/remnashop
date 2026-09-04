import { apiGet, apiPost, apiPut } from "@shared/api/http";

export type ReferralAccrualStrategy = "FIRST_PAYMENT" | "EVERY_PAYMENT";
export type ReferralRewardType = "EXTRA_DAYS" | "POINTS";

export interface ReferralSettings {
  enabled: boolean;
  max_level: number;
  accrual_strategy: ReferralAccrualStrategy;
  reward_type: ReferralRewardType;
  // Level (1..max_level) -> reward amount. JSON object keys are always
  // strings on the wire even though the backend's dict is keyed by int.
  reward_amounts: Record<string, string>;
}

export function getReferralSettings(signal?: AbortSignal): Promise<ReferralSettings> {
  return apiGet<ReferralSettings>("/referrals/settings", signal);
}

export interface UpdateReferralSettingsRequest {
  enabled?: boolean;
  max_level?: number;
  accrual_strategy?: ReferralAccrualStrategy;
  reward_type?: ReferralRewardType;
  reward_amounts?: Record<string, string>;
}

export function updateReferralSettings(payload: UpdateReferralSettingsRequest): Promise<ReferralSettings> {
  return apiPut<ReferralSettings, UpdateReferralSettingsRequest>("/referrals/settings", payload);
}

export interface ReferralReward {
  type: ReferralRewardType;
  amount: string;
  created_at: string | null;
}

export interface ReferralStats {
  referral_code: string | null;
  referrer_id: number | null;
  points: string;
  counts_by_level: Record<string, number>;
  rewards: ReferralReward[];
}

export function getUserReferralStats(userId: number, signal?: AbortSignal): Promise<ReferralStats> {
  return apiGet<ReferralStats>(`/users/${userId}/referrals`, signal);
}

export function adjustUserPoints(userId: number, delta: string): Promise<ReferralStats> {
  return apiPost<ReferralStats, { delta: string }>(`/users/${userId}/points`, { delta });
}
