import { apiDelete, apiGet, apiPatch, apiPost } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";

import type { AuthResult } from "./api";

export interface Passkey {
  id: number;
  name: string;
  device_type: string;
  backed_up: boolean;
  created_at: string;
  last_used_at: string | null;
}

export function getPasskeys(signal?: AbortSignal): Promise<Passkey[]> {
  return apiGet<ListResponse<Passkey>>("/auth/passkeys", signal).then((response) => response.items);
}

export function getPasskeyRegistrationOptions(
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  return apiGet<Record<string, unknown>>("/auth/passkeys/register/options", signal);
}

export function verifyPasskeyRegistration(
  credential: Record<string, unknown>,
  name: string | null,
): Promise<Passkey> {
  return apiPost<Passkey, { credential: Record<string, unknown>; name: string | null }>(
    "/auth/passkeys/register/verify",
    { credential, name },
  );
}

export function renamePasskey(id: number, name: string): Promise<Passkey> {
  return apiPatch<Passkey, { name: string }>(`/auth/passkeys/${id}`, { name });
}

export function deletePasskey(id: number): Promise<void> {
  return apiDelete<void>(`/auth/passkeys/${id}`);
}

export function getPasskeyAuthenticationOptions(): Promise<Record<string, unknown>> {
  return apiGet<Record<string, unknown>>("/auth/passkeys/authenticate/options");
}

export function verifyPasskeyAuthentication(
  credential: Record<string, unknown>,
): Promise<AuthResult> {
  return apiPost<AuthResult, { credential: Record<string, unknown> }>(
    "/auth/passkeys/authenticate/verify",
    { credential },
  );
}
