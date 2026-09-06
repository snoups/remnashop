import { apiGet, apiPost } from "@shared/api/http";
import type { Role } from "@shared/types/rbac";

export interface AuthStatus {
  is_login_allowed: boolean;
  is_register_allowed: boolean;
  oauth_providers: Record<string, boolean>;
  oidc_display_name: string | null;
  is_password_login_enabled: boolean;
  is_passkey_login_enabled: boolean;
}

export interface AuthResult {
  id: number;
  login: string;
  role: Role;
  access_token: string;
}

export interface BootstrapOwnerPayload {
  login: string;
  password: string;
}

export interface LoginPayload {
  login: string;
  password: string;
}

export function getAuthStatus(signal?: AbortSignal): Promise<AuthStatus> {
  return apiGet<AuthStatus>("/auth/status", signal);
}

export function bootstrapOwner(payload: BootstrapOwnerPayload): Promise<AuthResult> {
  return apiPost<AuthResult, BootstrapOwnerPayload>("/auth/bootstrap", payload);
}

export function login(payload: LoginPayload): Promise<AuthResult> {
  return apiPost<AuthResult, LoginPayload>("/auth/login", payload);
}
