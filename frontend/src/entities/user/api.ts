import { apiDelete, apiGet, apiPatch, apiPost } from "@shared/api/http";
import type { Permission, Role } from "@shared/types/rbac";

export interface CurrentUser {
  id: number;
  login: string | null;
  name: string;
  role: Role;
  effective_permissions: Permission[];
}

export interface UpdateOwnProfileRequest {
  name?: string;
  current_password?: string;
  new_password?: string;
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
  referral_code?: string | null;
  points: string;
  is_trial_available: boolean;
  created_at: string | null;
}

export const DEFAULT_PAGE_SIZE = 50;

export interface UserListPage {
  items: UserListItem[];
  total: number;
}

export interface UserListFilters {
  search?: string;
  role?: Role;
  isBlocked?: boolean;
  page?: number;
  pageSize?: number;
}

export function listUsers(
  filters: UserListFilters = {},
  signal?: AbortSignal,
): Promise<UserListPage> {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.role) params.set("role", filters.role);
  if (filters.isBlocked !== undefined) params.set("is_blocked", String(filters.isBlocked));
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<UserListPage>(`/users?${params.toString()}`, signal);
}

export function deleteUser(userId: number): Promise<void> {
  return apiDelete<void>(`/users/${userId}`);
}

export function blockUser(userId: number): Promise<UserListItem> {
  return apiPost<UserListItem, Record<string, never>>(`/users/${userId}/block`, {});
}

export function unblockUser(userId: number): Promise<UserListItem> {
  return apiPost<UserListItem, Record<string, never>>(`/users/${userId}/unblock`, {});
}

export interface UnblockAllResult {
  unblocked: number;
}

export function unblockAllUsers(): Promise<UnblockAllResult> {
  return apiPost<UnblockAllResult, Record<string, never>>("/users/unblock-all", {});
}
