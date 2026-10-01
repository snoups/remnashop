import { apiGet, apiPatch, apiPost } from "@shared/api/http";

export type ReferralAccrualStrategy = "FIRST_PAYMENT" | "EVERY_PAYMENT";
export type ReferralRewardType = "EXTRA_DAYS" | "POINTS";
export type ReferralRewardStrategy = "AMOUNT" | "PERCENT";

export interface ReferralSettings {
  enabled: boolean;
  max_level: number;
  accrual_strategy: ReferralAccrualStrategy;
  reward_type: ReferralRewardType;
  reward_strategy: ReferralRewardStrategy;
  // Level (1..max_level) -> reward amount. JSON object keys are always
  // strings on the wire even though the backend's dict is keyed by int.
  reward_amounts: Record<string, string>;
  // pricing's anchor: a PERCENT points reward is counted from the payment in it
  anchor_currency: string | null;
}

export function getReferralSettings(signal?: AbortSignal): Promise<ReferralSettings> {
  return apiGet<ReferralSettings>("/referrals/settings", signal);
}

export interface UpdateReferralSettingsRequest {
  enabled?: boolean;
  max_level?: number;
  accrual_strategy?: ReferralAccrualStrategy;
  reward_type?: ReferralRewardType;
  reward_strategy?: ReferralRewardStrategy;
  reward_amounts?: Record<string, string>;
}

export function updateReferralSettings(payload: UpdateReferralSettingsRequest): Promise<ReferralSettings> {
  return apiPatch<ReferralSettings, UpdateReferralSettingsRequest>("/referrals/settings", payload);
}

export function resetReferralSettings(): Promise<ReferralSettings> {
  return apiPost<ReferralSettings, Record<string, never>>("/referrals/settings/actions/reset", {});
}

export interface ReferralReward {
  type: ReferralRewardType;
  amount: string;
  created_at: string | null;
  /** whose payment earned it; admin endpoints only */
  buyer?: ReferralUser | null;
  /** buyer's depth below the rewarded user */
  level?: number | null;
}

export interface ReferralStats {
  referral_code: string | null;
  referrer_id: number | null;
  points: string;
  counts_by_level: Record<string, number>;
  rewards: ReferralReward[];
  /** admin endpoints only */
  referrer?: ReferralUser | null;
}

/** what the user's downline has paid, in the pricing anchor currency */
export interface ReferralRevenue {
  amount: string;
  currency: string;
  paying_count: number;
}

export function getUserReferralRevenue(userId: number, signal?: AbortSignal): Promise<ReferralRevenue> {
  return apiGet<ReferralRevenue>(`/users/${userId}/referrals/revenue`, signal);
}

export function getUserReferralStats(userId: number, signal?: AbortSignal): Promise<ReferralStats> {
  return apiGet<ReferralStats>(`/users/${userId}/referrals`, signal);
}

export function adjustUserPoints(userId: number, delta: string): Promise<ReferralStats> {
  return apiPost<ReferralStats, { delta: string }>(`/users/${userId}/actions/adjust-points`, { delta });
}

export function resetUserReferralCode(userId: number): Promise<ReferralStats> {
  return apiPost<ReferralStats, Record<string, never>>(`/users/${userId}/referral-code/actions/reset`, {});
}

export interface ReferralLinks {
  bot_url: string | null;
  webcabinet_url: string | null;
}

export function getUserReferralLinks(userId: number, signal?: AbortSignal): Promise<ReferralLinks> {
  return apiGet<ReferralLinks>(`/users/${userId}/referral-links`, signal);
}

export const REFERRALS_PAGE_SIZE = 50;

export interface ReferralUser {
  id: number;
  name: string;
  username: string | null;
  telegram_id: number | null;
  email: string | null;
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
  search?: string;
  hasRewards?: boolean;
  rewardType?: ReferralRewardType;
  page?: number;
  pageSize?: number;
}

export function listReferrals(filters: ReferralListFilters = {}, signal?: AbortSignal): Promise<ReferralListPage> {
  const params = new URLSearchParams();
  if (filters.level) params.set("level", String(filters.level));
  if (filters.createdFrom) params.set("created_from", filters.createdFrom);
  if (filters.search) params.set("search", filters.search);
  if (filters.hasRewards !== undefined) params.set("has_rewards", String(filters.hasRewards));
  if (filters.rewardType) params.set("reward_type", filters.rewardType);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? REFERRALS_PAGE_SIZE));
  return apiGet<ReferralListPage>(`/referrals?${params.toString()}`, signal);
}

export interface ReferralSummary {
  total_count: number;
  referrers_count: number;
  rewarded_count: number;
  conversion_rate: string;
  reward_amounts: Partial<Record<ReferralRewardType, string>>;
}

export function getReferralSummary(
  /** createdTo: the summary as it looked at that moment (later referrals and rewards left out) */
  filters: ReferralListFilters & { createdTo?: string } = {},
  signal?: AbortSignal,
): Promise<ReferralSummary> {
  const params = new URLSearchParams();
  if (filters.level) params.set("level", String(filters.level));
  if (filters.createdFrom) params.set("created_from", filters.createdFrom);
  if (filters.createdTo) params.set("created_to", filters.createdTo);
  if (filters.search) params.set("search", filters.search);
  if (filters.hasRewards !== undefined) params.set("has_rewards", String(filters.hasRewards));
  if (filters.rewardType) params.set("reward_type", filters.rewardType);
  return apiGet<ReferralSummary>(`/referrals/summary?${params.toString()}`, signal);
}

export interface InvitedUser {
  user: ReferralUser | null;
  /** direct inviter, set only below the first level */
  via: ReferralUser | null;
  level: number;
  created_at: string | null;
  reward_amounts: Partial<Record<ReferralRewardType, string>>;
}

export interface InvitedUserPage {
  items: InvitedUser[];
  total: number;
}

export interface InvitedUserFilters {
  level?: number;
  search?: string;
  page?: number;
  pageSize?: number;
}

export function listInvitedUsers(
  userId: number,
  filters: InvitedUserFilters = {},
  signal?: AbortSignal,
): Promise<InvitedUserPage> {
  const params = new URLSearchParams();
  if (filters.level) params.set("level", String(filters.level));
  if (filters.search) params.set("search", filters.search);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? REFERRALS_PAGE_SIZE));
  return apiGet<InvitedUserPage>(`/users/${userId}/referrals/invited?${params.toString()}`, signal);
}
