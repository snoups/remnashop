import { apiDelete, apiGet, apiPatch, apiPost } from "@shared/api/http";
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
  created_at: string | null;
  permission_grants: Permission[];
  permission_revokes: Permission[];
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

export function listAdmins(): Promise<Admin[]> {
  return apiGet<Admin[]>("/admins");
}

export function createAdmin(payload: CreateAdminPayload): Promise<AdminWithPassword> {
  return apiPost<AdminWithPassword, CreateAdminPayload>("/admins", payload);
}

export function promoteAdmin(payload: PromoteAdminPayload): Promise<AdminPromoteResult> {
  return apiPost<AdminPromoteResult, PromoteAdminPayload>("/admins/promote", payload);
}

export function updateAdmin(userId: number, payload: UpdateAdminPayload): Promise<Admin> {
  return apiPatch<Admin, UpdateAdminPayload>(`/admins/${userId}`, payload);
}

export function demoteAdmin(userId: number): Promise<Admin> {
  return apiPost<Admin, Record<string, never>>(`/admins/${userId}/demote`, {});
}

export function deleteAdmin(userId: number): Promise<void> {
  return apiDelete<void>(`/admins/${userId}`);
}
