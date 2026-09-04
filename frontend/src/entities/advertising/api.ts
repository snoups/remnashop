import { apiDelete, apiGet, apiPatch, apiPost } from "@shared/api/http";

export type AdLinkChannel = "BOT" | "WEBCABINET";

export interface AdLink {
  id: number;
  name: string;
  code: string;
  cost: string;
  cost_currency: string;
  is_active: boolean;
  note: string | null;
  created_by: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export const DEFAULT_PAGE_SIZE = 50;

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
  note?: string | null;
}

export function createAdLink(payload: CreateAdLinkRequest): Promise<AdLink> {
  return apiPost<AdLink, CreateAdLinkRequest>("/advertising/links", payload);
}

export interface UpdateAdLinkRequest {
  name?: string;
  cost?: string;
  cost_currency?: string;
  is_active?: boolean;
  note?: string | null;
}

export function updateAdLink(adLinkId: number, payload: UpdateAdLinkRequest): Promise<AdLink> {
  return apiPatch<AdLink, UpdateAdLinkRequest>(`/advertising/links/${adLinkId}`, payload);
}

export function deleteAdLink(adLinkId: number): Promise<void> {
  return apiDelete<void>(`/advertising/links/${adLinkId}`);
}

export function generateAdLinkCode(): Promise<string> {
  return apiPost<{ code: string }, Record<string, never>>("/advertising/links/generate-code", {}).then(
    (result) => result.code,
  );
}

export interface AdLinkStats {
  attributions_count: number;
  attributions_by_channel: Record<string, number>;
  paid_count: number;
  conversion_rate: string;
  revenue: string;
  revenue_by_currency: Record<string, string>;
  cost: string;
  report_currency: string;
  cpa: string | null;
  roi: string | null;
}

export function getAdLinkStats(adLinkId: number, signal?: AbortSignal): Promise<AdLinkStats> {
  return apiGet<AdLinkStats>(`/advertising/links/${adLinkId}/stats`, signal);
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
