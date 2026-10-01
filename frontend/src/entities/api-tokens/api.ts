import { apiDelete, apiGet, apiPost } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";
import type { Permission } from "@shared/types/rbac";

export interface ApiToken {
  id: number;
  name: string;
  permissions: Permission[];
  last_used_at: string | null;
  created_at: string;
  expires_at: string | null;
}

export interface CreatedApiToken {
  token: ApiToken;
  secret: string;
}

export function listApiTokens(signal?: AbortSignal): Promise<ApiToken[]> {
  return apiGet<ListResponse<ApiToken>>("/api-tokens", signal).then((response) => response.items);
}

export function createApiToken(
  name: string,
  permissions: Permission[],
  expiresInDays: number | null,
): Promise<CreatedApiToken> {
  return apiPost<CreatedApiToken, { name: string; permissions: Permission[]; expires_in_days: number | null }>(
    "/api-tokens",
    { name, permissions, expires_in_days: expiresInDays },
  );
}

export function revokeApiToken(id: number): Promise<void> {
  return apiDelete<void>(`/api-tokens/${id}`);
}
