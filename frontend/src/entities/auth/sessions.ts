import { apiDelete, apiGet } from "@shared/api/http";

export interface Session {
  id: number;
  ip_address: string;
  user_agent: string | null;
  created_at: string;
  last_used_at: string;
  expires_at: string;
}

export function listOwnSessions(): Promise<Session[]> {
  return apiGet<Session[]>("/auth/sessions");
}

export function revokeOwnSession(sessionId: number): Promise<void> {
  return apiDelete<void>(`/auth/sessions/${sessionId}`);
}

export function listUserSessions(userId: number): Promise<Session[]> {
  return apiGet<Session[]>(`/auth/sessions/users/${userId}`);
}

export function revokeUserSession(userId: number, sessionId: number): Promise<void> {
  return apiDelete<void>(`/auth/sessions/users/${userId}/${sessionId}`);
}
