import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@shared/api/http";
import type { Permission, Role } from "@shared/types/rbac";

export interface CurrentUser {
  id: number;
  login: string | null;
  name: string;
  role: Role;
  effective_permissions: Permission[];
  password_change_required: boolean;
  language: string;
}

export interface UpdateOwnProfileRequest {
  name?: string;
  current_password?: string;
  new_password?: string;
  language?: string;
}

export function getCurrentUser(signal?: AbortSignal): Promise<CurrentUser> {
  return apiGet<CurrentUser>("/users/me", signal);
}

export function updateOwnProfile(payload: UpdateOwnProfileRequest): Promise<CurrentUser> {
  return apiPatch<CurrentUser, UpdateOwnProfileRequest>("/users/me", payload);
}

export interface UserListItem {
  id: number;
  name: string;
  role: Role;
  telegram_id: number | null;
  username: string | null;
  email: string | null;
  login: string | null;
  language: string;
  is_blocked: boolean;
  personal_discount: number;
  purchase_discount: number;
  loyalty_discount: number;
  referral_code?: string | null;
  points: string;
  bonus_days: number;
  is_trial_available: boolean;
  created_at: string | null;
  /** set once the account is soft-deleted; name and contacts are wiped then */
  deleted_at?: string | null;
  email_undeliverable_at?: string | null;
  // list endpoint only
  active_subscriptions?: number;
  limited_subscriptions?: number;
  expired_subscriptions?: number;
}

export const DEFAULT_PAGE_SIZE = 50;

export interface UserListPage {
  items: UserListItem[];
  total: number;
}

export type UserSort = "created_at" | "points" | "discount" | "name" | "channels" | "subscriptions";

// exclude: live accounts only (the default); include: both; only: deleted ones
export type DeletedFilter = "exclude" | "include" | "only";

// which blacklist a blocked user is on: the manual list or external sources
export type BlockedBy = "manual" | "lists";

export interface UserListFilters {
  search?: string;
  includeStaff?: boolean;
  blockedBy?: BlockedBy;
  deleted?: DeletedFilter;
  hasSubscription?: boolean;
  isTrialAvailable?: boolean;
  sort?: UserSort;
  descending?: boolean;
  page?: number;
  pageSize?: number;
}

export interface UserListStats {
  total: number;
  new: number;
  subscribed: number;
  blocked: number;
  /** registrations in the 7 days before `new`'s window */
  new_previous: number;
  /** registrations over the last 30 days */
  total_growth: number;
}

export function listUsers(
  filters: UserListFilters = {},
  signal?: AbortSignal,
): Promise<UserListPage> {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.includeStaff) params.set("include_staff", "true");
  if (filters.blockedBy) params.set("blocked_by", filters.blockedBy);
  if (filters.deleted) params.set("deleted", filters.deleted);
  if (filters.hasSubscription !== undefined) params.set("has_subscription", String(filters.hasSubscription));
  if (filters.isTrialAvailable !== undefined) params.set("is_trial_available", String(filters.isTrialAvailable));
  if (filters.sort) params.set("sort", filters.sort);
  if (filters.descending !== undefined) params.set("descending", String(filters.descending));
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<UserListPage>(`/users?${params.toString()}`, signal);
}

export function getUser(userId: number, signal?: AbortSignal): Promise<UserListItem> {
  return apiGet<UserListItem>(`/users/${userId}`, signal);
}

export function getUserListStats(includeStaff: boolean, signal?: AbortSignal): Promise<UserListStats> {
  return apiGet<UserListStats>(`/users/summary${includeStaff ? "?include_staff=true" : ""}`, signal);
}

export function deleteUser(userId: number): Promise<void> {
  return apiDelete<void>(`/users/${userId}`);
}

export function setUserDiscount(
  userId: number,
  discounts: { personal_discount?: number; purchase_discount?: number },
): Promise<UserListItem> {
  return apiPatch<UserListItem, typeof discounts>(`/users/${userId}/discount`, discounts);
}

export function blockUser(userId: number): Promise<UserListItem> {
  return apiPost<UserListItem, Record<string, never>>(`/users/${userId}/actions/block`, {});
}

export function clearEmailUndeliverable(userId: number): Promise<UserListItem> {
  return apiPost<UserListItem, Record<string, never>>(`/users/${userId}/actions/clear-email-undeliverable`, {});
}

export function unblockUser(userId: number): Promise<UserListItem> {
  return apiPost<UserListItem, Record<string, never>>(`/users/${userId}/actions/unblock`, {});
}

export type MergeSide = "source" | "target";

export interface MergeConflict {
  key: string;
  source_value: string | null;
  target_value: string | null;
  forced: MergeSide | null;
}

export interface MergePreview {
  source: UserListItem;
  target: UserListItem;
  conflicts: MergeConflict[];
  /** keeping this side's inviter would loop, so the merge drops the link */
  referrer_cycles: { side: MergeSide; referrer_id: number }[];
  fingerprint: string;
  source_counts: {
    subscriptions: number;
    transactions: number;
    referrals: number;
    passkeys: number;
    oauth_identities: number;
  };
}

export function getMergePreview(targetId: number, sourceId: number, signal?: AbortSignal): Promise<MergePreview> {
  return apiGet<MergePreview>(`/users/${targetId}/merge-preview?source_id=${sourceId}`, signal);
}

export function mergeUsers(
  targetId: number,
  sourceId: number,
  choices: Record<string, MergeSide>,
  fingerprint: string,
): Promise<UserListItem> {
  return apiPost<UserListItem, { source_id: number; choices: Record<string, MergeSide>; fingerprint: string }>(
    `/users/${targetId}/actions/merge`,
    { source_id: sourceId, choices, fingerprint },
  );
}

export function bindUserTelegram(userId: number, telegramId: number): Promise<UserListItem> {
  return apiPut<UserListItem, { telegram_id: number }>(`/users/${userId}/telegram`, { telegram_id: telegramId });
}
