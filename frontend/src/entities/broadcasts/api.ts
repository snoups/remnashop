import { apiDelete, apiGet, apiGetRaw, apiPost, apiPut, apiUpload } from "@shared/api/http";
import type { ListResponse } from "@shared/api/http";
import type { VariableOption } from "@entities/dialogs/api";

export type BroadcastStatus = "DRAFT" | "SCHEDULED" | "SENDING" | "COMPLETED" | "CANCELED" | "FAILED";
export type BroadcastCategory = "SERVICE" | "MARKETING";
export type BroadcastRecipientStatus = "PENDING" | "SENT" | "FAILED" | "BLOCKED" | "CANCELED" | "RECALLED";
export type BroadcastButtonKind = "URL" | "PROMOCODE" | "MENU";
export type BroadcastMediaType = "PHOTO" | "VIDEO" | "ANIMATION" | "DOCUMENT";
export type SubscriptionFilter = "ACTIVE" | "TRIAL" | "EXPIRED" | "LIMITED" | "NONE";
export type BroadcastDelivery = "TELEGRAM" | "EMAIL" | "ALL";
export type BroadcastChannel = "TELEGRAM" | "EMAIL";

export interface BroadcastAudience {
  user_ids: number[];
  subscription: SubscriptionFilter[];
  plan_ids: number[];
  expires_within_days: number | null;
  expired_within_days: number | null;
  not_connected_within_days: number | null;
  paid: boolean | null;
  locales: string[];
  registered_from: string | null;
  registered_to: string | null;
  ad_link_ids: number[];
  referred: boolean | null;
  has_telegram: boolean | null;
  has_email: boolean | null;
}

export interface BroadcastContent {
  text: string;
  button_labels: string[];
}

export interface BroadcastEmailContent {
  subject: string;
  html: string;
}

export interface BroadcastButton {
  kind: BroadcastButtonKind;
  url: string | null;
  icon_custom_emoji_id: string | null;
}

export interface Broadcast {
  id: number;
  title: string | null;
  status: BroadcastStatus;
  category: BroadcastCategory;
  audience: BroadcastAudience;
  default_locale: string;
  delivery: BroadcastDelivery;
  email_fallback: boolean;
  contents: Record<string, BroadcastContent>;
  email_contents: Record<string, BroadcastEmailContent>;
  buttons: BroadcastButton[];
  promocode_id: number | null;
  post_to_channel: boolean;
  has_channel_post: boolean;
  recall_requested: boolean;
  recall_requested_at: string | null;
  // only on single-broadcast reads
  recallable_count?: number | null;
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
  delivery: BroadcastDelivery;
  email_fallback: boolean;
  contents: Record<string, BroadcastContent>;
  email_contents: Record<string, BroadcastEmailContent>;
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
  channel: BroadcastChannel;
  email: string | null;
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
  reachable_by_email: number;
}

export interface AudiencePreview {
  total: number;
  by_locale: Record<string, number>;
  by_channel: Partial<Record<BroadcastChannel, number>>;
}

export const EMPTY_AUDIENCE: BroadcastAudience = {
  user_ids: [],
  subscription: [],
  plan_ids: [],
  expires_within_days: null,
  expired_within_days: null,
  not_connected_within_days: null,
  paid: null,
  locales: [],
  registered_from: null,
  registered_to: null,
  ad_link_ids: [],
  referred: null,
  has_telegram: null,
  has_email: null,
};

export const DEFAULT_PAGE_SIZE = 50;

// Telegram deletes bot messages only within 48 hours
export const RECALL_WINDOW_MS = 48 * 3600 * 1000;
// matches RECALL_REPEAT_AFTER on the backend
export const RECALL_REPEAT_AFTER_MS = 5 * 60 * 1000;

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
  return apiUpload<Broadcast>(`/broadcasts/${id}/media`, file);
}

export function deleteBroadcastMedia(id: number): Promise<Broadcast> {
  return apiDelete<Broadcast>(`/broadcasts/${id}/media`);
}

export interface BroadcastEmailImage {
  id: number;
  content_type: string;
  size_bytes: number;
}

export function uploadEmailImage(broadcastId: number, file: File): Promise<BroadcastEmailImage> {
  return apiUpload<BroadcastEmailImage>(`/broadcasts/${broadcastId}/email-images`, file, "POST");
}

export async function fetchEmailImage(broadcastId: number, imageId: number): Promise<Blob> {
  const response = await apiGetRaw(`/broadcasts/${broadcastId}/email-images/${imageId}`);
  return response.blob();
}

export function previewAudience(
  audience: BroadcastAudience,
  category: BroadcastCategory,
  delivery: BroadcastDelivery,
  emailFallback: boolean,
  signal?: AbortSignal,
): Promise<AudiencePreview> {
  return apiPost<
    AudiencePreview,
    { audience: BroadcastAudience; category: BroadcastCategory; delivery: BroadcastDelivery; email_fallback: boolean }
  >(
    "/broadcasts/actions/preview-audience",
    { audience, category, delivery, email_fallback: emailFallback },
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

export interface BroadcastEmailPreview {
  subject: string;
  html: string;
  text: string;
}

export function previewBroadcastEmail(id: number, locale: string): Promise<BroadcastEmailPreview> {
  return apiPost<BroadcastEmailPreview, { locale: string }>(`/broadcasts/${id}/actions/preview-email`, { locale });
}

export function sendTestBroadcastEmail(id: number, locale: string, to: string): Promise<void> {
  return apiPost<void, { locale: string; to: string }>(`/broadcasts/${id}/actions/send-test-email`, { locale, to });
}

export interface BroadcastRecipientFilters {
  status?: BroadcastRecipientStatus;
  channel?: BroadcastChannel;
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
  if (filters.channel) params.set("channel", filters.channel);
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));
  return apiGet<ListResponse<BroadcastRecipient>>(`/broadcasts/${id}/recipients?${params.toString()}`, signal);
}
