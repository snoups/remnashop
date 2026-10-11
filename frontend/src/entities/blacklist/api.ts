import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";
import type { Role } from "@shared/types/rbac";

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

export function getBlacklist(signal?: AbortSignal): Promise<Blacklist> {
  return apiGet<Blacklist>("/blacklist", signal);
}

function entryPath(kind: BlacklistKind, value: string): string {
  return `/blacklist/entries/${kind}/${encodeURIComponent(value)}`;
}

export function addBlacklistEntry(kind: BlacklistKind, value: string): Promise<Blacklist> {
  return apiPut<Blacklist, Record<string, never>>(entryPath(kind, value), {});
}

export function removeBlacklistEntry(kind: BlacklistKind, value: string): Promise<Blacklist> {
  return apiDelete<Blacklist>(entryPath(kind, value));
}

export function listBlacklistSources(signal?: AbortSignal): Promise<BlacklistSource[]> {
  return apiGet<ListResponse<BlacklistSource>>("/blacklist/sources", signal).then((response) => response.items);
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

export function updateBlacklistSource(id: number, enabled: boolean): Promise<BlacklistSource> {
  return apiPatch<BlacklistSource, { enabled: boolean }>(`/blacklist/sources/${id}`, { enabled });
}

export function syncBlacklistSources(): Promise<void> {
  return apiPost<void, Record<string, never>>("/blacklist/sources/actions/sync", {});
}

export interface BlacklistOrigin {
  // null = the manual list
  source_id: number | null;
  source_name: string | null;
}

export interface BlacklistHit {
  kind: BlacklistKind;
  value: string;
  origins: BlacklistOrigin[];
}

// Same shape as the users list item, kept local so entities don't import each other.
export interface BlacklistMatchUser {
  id: number;
  name: string;
  role: Role;
  telegram_id: number | null;
  username: string | null;
  email: string | null;
  login: string | null;
  language: string;
  is_blocked: boolean;
  personal_discount: number;
  purchase_discount: number;
  loyalty_discount: number;
  points: string;
  bonus_days: number;
  is_trial_available: boolean;
  created_at: string | null;
}

export interface BlacklistMatch {
  user: BlacklistMatchUser;
  hits: BlacklistHit[];
}

export interface BlacklistMatchPage {
  items: BlacklistMatch[];
  total: number;
  all_total: number;
  manual_total: number;
  lists_total: number;
}

export interface BlacklistMatchFilters {
  search?: string;
  origin?: "manual" | "lists";
  page: number;
  pageSize: number;
}

export function listBlacklistMatches(
  filters: BlacklistMatchFilters,
  signal?: AbortSignal,
): Promise<BlacklistMatchPage> {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.origin) params.set("origin", filters.origin);
  params.set("page", String(filters.page));
  params.set("page_size", String(filters.pageSize));

  return apiGet<BlacklistMatchPage>(`/users/blacklist-matches?${params.toString()}`, signal);
}

// Drops the matched users' manual entries too; source-list matches are re-blocked on the next reconcile.
export function unblockBlacklistMatches(): Promise<{ unblocked: number }> {
  return apiPost<{ unblocked: number }, Record<string, never>>("/users/bulk/unblock-blacklist-matches", {});
}
