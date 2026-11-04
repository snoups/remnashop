import { apiDelete, apiGet, apiPost } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";

export interface Session {
  id: number;
  ip_address: string;
  user_agent: string | null;
  created_at: string;
  last_used_at: string;
  expires_at: string;
}

export function listOwnSessions(signal?: AbortSignal): Promise<Session[]> {
  return apiGet<ListResponse<Session>>("/auth/sessions", signal).then((response) => response.items);
}

export function revokeOwnSession(sessionId: number): Promise<void> {
  return apiDelete<void>(`/auth/sessions/${sessionId}`);
}

export function revokeOtherOwnSessions(): Promise<void> {
  return apiPost<void, Record<string, never>>("/auth/sessions/actions/revoke-others", {});
}

export function listUserSessions(userId: number, signal?: AbortSignal): Promise<Session[]> {
  return apiGet<ListResponse<Session>>(`/users/${userId}/sessions`, signal).then((response) => response.items);
}

export function revokeUserSession(userId: number, sessionId: number): Promise<void> {
  return apiDelete<void>(`/users/${userId}/sessions/${sessionId}`);
}
