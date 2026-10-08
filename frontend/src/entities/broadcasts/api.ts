import { apiDelete, apiGet, apiPost, apiPut, apiUpload } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";
import type { VariableOption } from "@entities/dialogs/api";

export type BroadcastStatus = "DRAFT" | "SCHEDULED" | "SENDING" | "COMPLETED" | "CANCELED" | "FAILED";
export type BroadcastCategory = "SERVICE" | "MARKETING";
export type BroadcastRecipientStatus = "PENDING" | "SENT" | "FAILED" | "BLOCKED" | "CANCELED" | "RECALLED";
export type BroadcastButtonKind = "URL" | "PROMOCODE" | "MENU";
export type BroadcastMediaType = "PHOTO" | "VIDEO" | "ANIMATION" | "DOCUMENT";
export type SubscriptionFilter = "ACTIVE" | "TRIAL" | "EXPIRED" | "NONE";

export interface BroadcastAudience {
  user_ids: number[];
  subscription: SubscriptionFilter[];
  plan_ids: number[];
  expires_within_days: number | null;
  expired_within_days: number | null;
  paid: boolean | null;
  locales: string[];
  registered_from: string | null;
  registered_to: string | null;
  ad_link_ids: number[];
  referred: boolean | null;
}

export interface BroadcastContent {
  text: string;
  button_labels: string[];
}

export interface BroadcastButton {
  kind: BroadcastButtonKind;
  url: string | null;
}

export interface Broadcast {
  id: number;
  title: string | null;
  status: BroadcastStatus;
  category: BroadcastCategory;
  audience: BroadcastAudience;
  default_locale: string;
  contents: Record<string, BroadcastContent>;
  buttons: BroadcastButton[];
  promocode_id: number | null;
  post_to_channel: boolean;
  has_channel_post: boolean;
  recall_requested: boolean;
  media_type: BroadcastMediaType | null;
  media_size_bytes: number | null;
  scheduled_at: string | null;
  created_by: number | null;
  created_by_name: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_count: number;
  sent_count: number;
  failed_count: number;
  blocked_count: number;
  recalled_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface BroadcastInput {
  title: string | null;
  category: BroadcastCategory;
  audience: BroadcastAudience;
  default_locale: string;
  contents: Record<string, BroadcastContent>;
  buttons: BroadcastButton[];
  promocode_id: number | null;
  post_to_channel: boolean;
}

export interface BroadcastRecipient {
  id: number;
  user_id: number;
  user_name: string;
  username: string | null;
  telegram_id: number | null;
  language: string;
  status: BroadcastRecipientStatus;
  attempts: number;
  error: string | null;
  sent_at: string | null;
}

export interface BroadcastSummary {
  by_status: Partial<Record<BroadcastStatus, number>>;
  next_scheduled_at: string | null;
  delivered_30d: number;
  processed_30d: number;
  opted_out: number;
  reachable_customers: number;
}

export interface AudiencePreview {
  total: number;
  by_locale: Record<string, number>;
}

export const EMPTY_AUDIENCE: BroadcastAudience = {
  user_ids: [],
  subscription: [],
  plan_ids: [],
  expires_within_days: null,
  expired_within_days: null,
  paid: null,
  locales: [],
  registered_from: null,
  registered_to: null,
  ad_link_ids: [],
  referred: null,
};

export const DEFAULT_PAGE_SIZE = 50;

// Telegram deletes bot messages only within 48 hours
export const RECALL_WINDOW_MS = 48 * 3600 * 1000;

export const BROADCAST_VARIABLES: VariableOption[] = [
  { name: "name", category: "user" },
  { name: "username", category: "user" },
  { name: "points", category: "user" },
  { name: "bonus_days", category: "user" },
  { name: "plan", category: "subscription" },
  { name: "expire_date", category: "subscription" },
  { name: "days_left", category: "subscription" },
  { name: "promocode", category: "promo" },
];

export interface BroadcastListFilters {
  statuses?: BroadcastStatus[];
  search?: string;
  page?: number;
  pageSize?: number;
}

export function listBroadcasts(filters: BroadcastListFilters = {}, signal?: AbortSignal): Promise<ListResponse<Broadcast>> {
  const params = new URLSearchParams();
  for (const status of filters.statuses ?? []) params.append("status", status);
  if (filters.search) params.set("search", filters.search);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));
  return apiGet<ListResponse<Broadcast>>(`/broadcasts?${params.toString()}`, signal);
}

export function getBroadcast(id: number, signal?: AbortSignal): Promise<Broadcast> {
  return apiGet<Broadcast>(`/broadcasts/${id}`, signal);
}

export function getBroadcastSummary(signal?: AbortSignal): Promise<BroadcastSummary> {
  return apiGet<BroadcastSummary>("/broadcasts/summary", signal);
}

export function createBroadcast(body: BroadcastInput): Promise<Broadcast> {
  return apiPost<Broadcast, BroadcastInput>("/broadcasts", body);
}

export function updateBroadcast(id: number, body: BroadcastInput): Promise<Broadcast> {
  return apiPut<Broadcast, BroadcastInput>(`/broadcasts/${id}`, body);
}

export function deleteBroadcast(id: number): Promise<void> {
  return apiDelete<void>(`/broadcasts/${id}`);
}

export function uploadBroadcastMedia(id: number, file: File): Promise<Broadcast> {
  const form = new FormData();
  form.append("file", file);
  return apiUpload<Broadcast>(`/broadcasts/${id}/media`, form);
}

export function deleteBroadcastMedia(id: number): Promise<Broadcast> {
  return apiDelete<Broadcast>(`/broadcasts/${id}/media`);
}

export function previewAudience(
  audience: BroadcastAudience,
  category: BroadcastCategory,
  signal?: AbortSignal,
): Promise<AudiencePreview> {
  return apiPost<AudiencePreview, { audience: BroadcastAudience; category: BroadcastCategory }>(
    "/broadcasts/actions/preview-audience",
    { audience, category },
    signal,
  );
}

export function sendBroadcast(id: number, scheduledAt: string | null): Promise<Broadcast> {
  return apiPost<Broadcast, { scheduled_at: string | null }>(`/broadcasts/${id}/actions/send`, {
    scheduled_at: scheduledAt,
  });
}

export function cancelBroadcast(id: number): Promise<Broadcast> {
  return apiPost<Broadcast, Record<string, never>>(`/broadcasts/${id}/actions/cancel`, {});
}

export function retryBroadcast(id: number): Promise<Broadcast> {
  return apiPost<Broadcast, Record<string, never>>(`/broadcasts/${id}/actions/retry`, {});
}

export function recallBroadcast(id: number): Promise<Broadcast> {
  return apiPost<Broadcast, Record<string, never>>(`/broadcasts/${id}/actions/recall`, {});
}

export function sendTestBroadcast(id: number): Promise<void> {
  return apiPost<void, Record<string, never>>(`/broadcasts/${id}/actions/send-test`, {});
}

export interface BroadcastRecipientFilters {
  status?: BroadcastRecipientStatus;
  page?: number;
  pageSize?: number;
}

export function listBroadcastRecipients(
  id: number,
  filters: BroadcastRecipientFilters = {},
  signal?: AbortSignal,
): Promise<ListResponse<BroadcastRecipient>> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));
  return apiGet<ListResponse<BroadcastRecipient>>(`/broadcasts/${id}/recipients?${params.toString()}`, signal);
}
