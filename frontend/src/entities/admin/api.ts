import { apiDelete, apiGet, apiPatch, apiPost } from "@shared/api/http";
import type { UserBase } from "@entities/user/api";
import type { ListResponse } from "@shared/api/http";
import type { Permission } from "@shared/types/rbac";

/** the user fields plus the permission breakdown */
export interface Admin extends UserBase {
  permission_grants: Permission[];
  permission_revokes: Permission[];
  role_permissions: Permission[];
  effective_permissions: Permission[];
}

export interface AdminWithPassword {
  admin: Admin;
  password: string;
}

export interface AdminPromoteResult {
  admin: Admin;
  password: string | null;
}

export interface CreateAdminPayload {
  login: string;
  permission_grants: Permission[];
  permission_revokes: Permission[];
}

export interface PromoteAdminPayload {
  user_id: number;
  login?: string;
}

export interface UpdateAdminPayload {
  permission_grants: Permission[];
  permission_revokes: Permission[];
}

export interface AdminList extends ListResponse<Admin> {
  /** admins who can still sign in once demoted (Telegram, email or OAuth) */
  customer_sign_in_ids: number[];
}

export function listAdmins(signal?: AbortSignal): Promise<AdminList> {
  return apiGet<AdminList>("/admins", signal);
}

export function createAdmin(payload: CreateAdminPayload): Promise<AdminWithPassword> {
  return apiPost<AdminWithPassword, CreateAdminPayload>("/admins", payload);
}

export function promoteAdmin(payload: PromoteAdminPayload): Promise<AdminPromoteResult> {
  return apiPost<AdminPromoteResult, PromoteAdminPayload>("/admins/actions/promote", payload);
}

export function updateAdmin(userId: number, payload: UpdateAdminPayload): Promise<Admin> {
  return apiPatch<Admin, UpdateAdminPayload>(`/admins/${userId}`, payload);
}

export interface AdminDetail extends Admin {
  /** Telegram, email or OAuth left once demoted */
  can_sign_in_after_demote: boolean;
}

export function getAdmin(userId: number, signal?: AbortSignal): Promise<AdminDetail> {
  return apiGet<AdminDetail>(`/admins/${userId}`, signal);
}

export function demoteAdmin(userId: number): Promise<UserBase> {
  return apiPost<UserBase, Record<string, never>>(`/admins/${userId}/actions/demote`, {});
}

export function deleteAdmin(userId: number): Promise<void> {
  return apiDelete<void>(`/admins/${userId}`);
}

export interface PermissionCatalogEntry {
  permission: Permission;
  resource: string;
  kind: "read" | "write";
  token_grantable: boolean;
  admin_default: boolean;
}

interface PermissionCatalogResponse {
  items: PermissionCatalogEntry[];
  total: number;
}

export function getPermissionCatalog(signal?: AbortSignal): Promise<PermissionCatalogEntry[]> {
  return apiGet<PermissionCatalogResponse>("/permissions/catalog", signal).then((response) => response.items);
}
