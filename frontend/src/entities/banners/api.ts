import { apiDelete, apiPost, apiUpload, BASE_URL } from "@shared/api/http";
import { getAccessToken } from "@shared/lib/token-storage";

export interface BannerMeta {
  name: string;
  locale: string;
  content_type: string;
  size_bytes: number;
}

export function uploadBanner(name: string, locale: string, file: File): Promise<BannerMeta> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<BannerMeta>(`/banners/${name}/${locale}`, formData);
}

export function restoreDefaultBanner(): Promise<null> {
  return apiPost<null, Record<string, never>>("/banners/actions/reset-default", {});
}

export function deleteBanner(name: string, locale: string): Promise<null> {
  return apiDelete<null>(`/banners/${name}/${locale}`);
}

// Not routed through apiGet: the response is a raw image, not JSON --
// apiGet/request() always call response.json(). Doesn't share request()'s
// 401-refresh-and-retry logic either, since this is a best-effort preview
// image, not a data-mutating call worth that complexity.
export async function fetchBannerImageBlob(name: string, locale: string, signal?: AbortSignal): Promise<Blob> {
  const token = getAccessToken();
  const response = await fetch(`${BASE_URL}/banners/${name}/${locale}/image`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch banner image: ${response.status}`);
  }
  return response.blob();
}
