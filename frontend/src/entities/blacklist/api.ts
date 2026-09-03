import { apiDelete, apiGet, apiPatch, apiPost } from "@shared/api/http";

export type BlacklistKind = "TELEGRAM_ID" | "EMAIL";

export interface Blacklist {
  telegram_ids: number[];
  emails: string[];
}

export interface BlacklistSource {
  id: number;
  url: string;
  name: string | null;
  enabled: boolean;
  entries_count: number;
  last_synced_at: string | null;
  last_error: string | null;
}

export function getBlacklist(): Promise<Blacklist> {
  return apiGet<Blacklist>("/blacklist");
}

export function addBlacklistEntry(kind: BlacklistKind, value: string): Promise<Blacklist> {
  return apiPost<Blacklist, { kind: BlacklistKind; value: string }>("/blacklist/entries", {
    kind,
    value,
  });
}

export function removeBlacklistEntry(kind: BlacklistKind, value: string): Promise<Blacklist> {
  return apiDelete<Blacklist, { kind: BlacklistKind; value: string }>("/blacklist/entries", {
    kind,
    value,
  });
}

export function listBlacklistSources(): Promise<BlacklistSource[]> {
  return apiGet<BlacklistSource[]>("/blacklist/sources");
}

export function addBlacklistSource(url: string, name?: string): Promise<BlacklistSource> {
  return apiPost<BlacklistSource, { url: string; name?: string }>("/blacklist/sources", {
    url,
    name,
  });
}

export function removeBlacklistSource(id: number): Promise<void> {
  return apiDelete<void>(`/blacklist/sources/${id}`);
}

export function toggleBlacklistSource(id: number, enabled: boolean): Promise<BlacklistSource> {
  return apiPatch<BlacklistSource, { enabled: boolean }>(`/blacklist/sources/${id}`, { enabled });
}

export function syncBlacklistSources(): Promise<void> {
  return apiPost<void, Record<string, never>>("/blacklist/sources/sync", {});
}
