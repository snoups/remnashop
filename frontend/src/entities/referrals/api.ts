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

export const REFERRALS_PAGE_SIZE = 50;

export interface ReferralUser {
  id: number;
  name: string;
  username: string | null;
  telegram_id: number | null;
}

export interface ReferralListItem {
  id: number;
  level: number;
  created_at: string;
  referred: ReferralUser | null;
  referrer: ReferralUser | null;
  reward_count: number;
  reward_amounts: Partial<Record<ReferralRewardType, string>>;
}

export interface ReferralListPage {
  items: ReferralListItem[];
  total: number;
}

export interface ReferralListFilters {
  level?: number;
  createdFrom?: string;
  page?: number;
  pageSize?: number;
}

export function listReferrals(filters: ReferralListFilters = {}, signal?: AbortSignal): Promise<ReferralListPage> {
  const params = new URLSearchParams();
  if (filters.level) params.set("level", String(filters.level));
  if (filters.createdFrom) params.set("created_from", filters.createdFrom);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? REFERRALS_PAGE_SIZE));
  return apiGet<ReferralListPage>(`/referrals?${params.toString()}`, signal);
}
