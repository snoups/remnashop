import { apiDelete, apiGet, apiUpload, BASE_URL } from "@shared/api/http";
import { getAccessToken } from "@shared/lib/token-storage";

export interface BannerMeta {
  name: string;
  locale: string;
  content_type: string;
  size_bytes: number;
}

export interface BannerListResult {
  banners: BannerMeta[];
  available_locales: string[];
}

export function listBanners(): Promise<BannerListResult> {
  return apiGet<BannerListResult>("/banners");
}

export function uploadBanner(name: string, locale: string, file: File): Promise<BannerMeta> {
  const formData = new FormData();
  formData.append("name", name);
  formData.append("locale", locale);
  formData.append("file", file);
  return apiUpload<BannerMeta>("/banners", formData);
}

export function deleteBanner(name: string, locale: string): Promise<null> {
  return apiDelete<null>(`/banners/${name}/${locale}`);
}

// Not routed through apiGet: the response is a raw image, not JSON --
// apiGet/request() always call response.json(). Doesn't share request()'s
// 401-refresh-and-retry logic either, since this is a best-effort preview
// image, not a data-mutating call worth that complexity.
export async function fetchBannerImageBlob(name: string, locale: string): Promise<Blob> {
  const token = getAccessToken();
  const response = await fetch(`${BASE_URL}/banners/${name}/${locale}/image`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch banner image: ${response.status}`);
  }
  return response.blob();
}
