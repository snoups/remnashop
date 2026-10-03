import { apiDelete, apiGet, apiPatch, apiPost } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";
import type { Permission, Role } from "@shared/types/rbac";

export interface Admin {
  id: number;
  login: string | null;
  name: string;
  role: Role;
  telegram_id: number | null;
  username: string | null;
  email: string | null;
  language: string;
  is_blocked: boolean;
  personal_discount: number;
  purchase_discount: number;
  points: string;
  is_trial_available: boolean;
  created_at: string | null;
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
  name: string;
  permission_grants: Permission[];
  permission_revokes: Permission[];
}

export interface PromoteAdminPayload {
  user_id?: number;
  email?: string;
  telegram_username?: string;
  login?: string;
  permission_grants: Permission[];
  permission_revokes: Permission[];
}

export interface UpdateAdminPayload {
  permission_grants: Permission[];
  permission_revokes: Permission[];
}

export function listAdmins(signal?: AbortSignal): Promise<Admin[]> {
  return apiGet<ListResponse<Admin>>("/admins", signal).then((response) => response.items);
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

export function demoteAdmin(userId: number): Promise<Admin> {
  return apiPost<Admin, Record<string, never>>(`/admins/${userId}/actions/demote`, {});
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
  entries: PermissionCatalogEntry[];
}

export function getPermissionCatalog(signal?: AbortSignal): Promise<PermissionCatalogEntry[]> {
  return apiGet<PermissionCatalogResponse>("/permissions/catalog", signal).then((response) => response.entries);
}
