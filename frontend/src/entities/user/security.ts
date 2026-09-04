import { apiGet, apiPut } from "@shared/api/http";

export interface SecuritySettings {
  ip_allowlist: string[];
}

export function getOwnSecurity(signal?: AbortSignal): Promise<SecuritySettings> {
  return apiGet<SecuritySettings>("/users/me/security", signal);
}

export function updateOwnSecurity(ipAllowlist: string[]): Promise<SecuritySettings> {
  return apiPut<SecuritySettings, { ip_allowlist: string[] }>("/users/me/security", {
    ip_allowlist: ipAllowlist,
  });
}
