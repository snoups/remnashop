import { apiDelete, apiGet, apiGetRaw, apiPatch, apiPost } from "@shared/api/http";

export type AdLinkChannel = "BOT" | "WEBCABINET";

export interface AdLink {
  id: number;
  name: string;
  code: string;
  cost: string;
  cost_currency: string;
  /** "0"–"100": share of attributed users' payments added to the cost */
  revenue_share_percent: string;
  is_active: boolean;
  allow_bot: boolean;
  allow_webcabinet: boolean;
  note: string | null;
  created_by: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export const DEFAULT_PAGE_SIZE = 50;

// mirror CreateAdLinkRequest.code in backend/app/modules/advertising/api/schemas.py
export const AD_LINK_CODE_PATTERN = /^[A-Za-z0-9_-]+$/;
export const AD_LINK_CODE_MAX_LENGTH = 48;

export interface AdLinkListPage {
  items: AdLink[];
  total: number;
}

export interface AdLinkListFilters {
  isActive?: boolean;
  page?: number;
  pageSize?: number;
}

export function listAdLinks(
  filters: AdLinkListFilters = {},
  signal?: AbortSignal,
): Promise<AdLinkListPage> {
  const params = new URLSearchParams();
  if (filters.isActive !== undefined) params.set("is_active", String(filters.isActive));
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? DEFAULT_PAGE_SIZE));

  return apiGet<AdLinkListPage>(`/advertising/links?${params.toString()}`, signal);
}

export interface CreateAdLinkRequest {
  name: string;
  code: string;
  cost?: string;
  cost_currency?: string;
  revenue_share_percent?: string;
  allow_bot?: boolean;
  allow_webcabinet?: boolean;
  note?: string | null;
}

export function createAdLink(payload: CreateAdLinkRequest): Promise<AdLink> {
  return apiPost<AdLink, CreateAdLinkRequest>("/advertising/links", payload);
}

export interface UpdateAdLinkRequest {
  name?: string;
  cost?: string;
  cost_currency?: string;
  revenue_share_percent?: string;
  is_active?: boolean;
  allow_bot?: boolean;
  allow_webcabinet?: boolean;
  /** "" clears it */
  note?: string;
}

export function updateAdLink(adLinkId: number, payload: UpdateAdLinkRequest): Promise<AdLink> {
  return apiPatch<AdLink, UpdateAdLinkRequest>(`/advertising/links/${adLinkId}`, payload);
}

export function deleteAdLink(adLinkId: number): Promise<void> {
  return apiDelete<void>(`/advertising/links/${adLinkId}`);
}

export function generateAdLinkCode(): Promise<string> {
  return apiPost<{ code: string }, Record<string, never>>("/advertising/links/actions/generate-code", {}).then(
    (result) => result.code,
  );
}

export interface AdLinkStats {
  attributions_count: number;
  attributions_by_channel: Partial<Record<AdLinkChannel, number>>;
  paid_count: number;
  conversion_rate: string;
  revenue: string;
  /** fixed_cost + revenue_share */
  cost: string;
  fixed_cost: string;
  revenue_share_percent: string;
  revenue_share: string;
  report_currency: string;
  cpa: string | null;
  roi: string | null;
  daily_registrations: { day: string; count: number; by_channel: Partial<Record<AdLinkChannel, number>> }[];
}

// createdFrom: ISO timestamp; counts only attributions made since then.
export function getAdLinkStats(
  adLinkId: number,
  createdFrom?: string,
  signal?: AbortSignal,
): Promise<AdLinkStats> {
  const params = new URLSearchParams();
  if (createdFrom) params.set("created_from", createdFrom);
  return apiGet<AdLinkStats>(`/advertising/links/${adLinkId}/stats?${params.toString()}`, signal);
}

export interface AdLinkPayout {
  report_currency: string;
  payments_count: number;
  revenue: string;
  revenue_share_percent: string;
  payout: string;
}

// paidFrom/paidTo: "YYYY-MM-DD", both days included
export function getAdLinkPayout(
  adLinkId: number,
  paidFrom: string,
  paidTo: string,
  signal?: AbortSignal,
): Promise<AdLinkPayout> {
  const params = new URLSearchParams({ paid_from: paidFrom, paid_to: paidTo });
  return apiGet<AdLinkPayout>(`/advertising/links/${adLinkId}/payout?${params.toString()}`, signal);
}

export interface AdLinkMetrics {
  ad_link_id: number;
  attributions_count: number;
  paid_count: number;
  revenue: string;
  cost: string;
  roi: string | null;
}

export interface AdvertisingSummary {
  report_currency: string;
  attributions_count: number;
  attributions_by_channel: Partial<Record<AdLinkChannel, number>>;
  paid_count: number;
  conversion_rate: string;
  revenue: string;
  cost: string;
  cpa: string | null;
  roi: string | null;
  links: AdLinkMetrics[];
}

export function getAdvertisingSummary(
  /** createdTo: the summary as it looked at that moment (later attributions and payments left out) */
  filters: { isActive?: boolean; createdFrom?: string; createdTo?: string },
  signal?: AbortSignal,
): Promise<AdvertisingSummary> {
  const params = new URLSearchParams();
  if (filters.isActive !== undefined) params.set("is_active", String(filters.isActive));
  if (filters.createdFrom) params.set("created_from", filters.createdFrom);
  if (filters.createdTo) params.set("created_to", filters.createdTo);
  return apiGet<AdvertisingSummary>(`/advertising/summary?${params.toString()}`, signal);
}

export interface AttributedUser {
  user_id: number;
  name: string;
  channel: AdLinkChannel;
  created_at: string;
  has_paid: boolean;
}

export interface AttributedUserPage {
  items: AttributedUser[];
  total: number;
}

export function listAdLinkAttributedUsers(
  adLinkId: number,
  page = 1,
  pageSize = DEFAULT_PAGE_SIZE,
  signal?: AbortSignal,
): Promise<AttributedUserPage> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return apiGet<AttributedUserPage>(`/advertising/links/${adLinkId}/users?${params.toString()}`, signal);
}

export interface UserAdAttribution {
  ad_link_id: number;
  name: string;
  code: string;
  channel: AdLinkChannel;
  attributed_at: string;
}

export function getUserAdAttribution(userId: number, signal?: AbortSignal): Promise<UserAdAttribution | null> {
  return apiGet<{ attribution: UserAdAttribution | null }>(`/users/${userId}/ad-attribution`, signal).then(
    (response) => response.attribution,
  );
}

// null = channel not allowed on the link, or its base URL isn't configured
export interface AdLinkShareUrls {
  bot_url: string | null;
  webcabinet_url: string | null;
}

export function getAdLinkShareUrls(adLinkId: number, signal?: AbortSignal): Promise<AdLinkShareUrls> {
  return apiGet<AdLinkShareUrls>(`/advertising/links/${adLinkId}/share`, signal);
}

export async function fetchAdLinkQr(adLinkId: number, channel: AdLinkChannel): Promise<Blob> {
  return (await apiGetRaw(`/advertising/links/${adLinkId}/qr?channel=${channel}`)).blob();
}
