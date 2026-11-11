import { apiDelete, apiGetRaw, apiPost, apiUpload } from "@shared/api/http";

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

export function restoreDefaultBanner(): Promise<BannerMeta> {
  return apiPost<BannerMeta, Record<string, never>>("/banners/actions/reset-default", {});
}

export function deleteBanner(name: string, locale: string): Promise<null> {
  return apiDelete<null>(`/banners/${name}/${locale}`);
}

/** The file the bot sends for this banner and language, and which one that is: the shared banner
 *  or the default language's stand in when this exact file is missing. */
export interface BannerPreview {
  blob: Blob;
  name: string;
  locale: string;
}

export async function fetchBannerPreview(name: string, locale: string, signal?: AbortSignal): Promise<BannerPreview> {
  const response = await apiGetRaw(`/banners/${name}/${locale}/image?fallback=true`, signal);
  return {
    blob: await response.blob(),
    name: response.headers.get("X-Banner-Name") ?? name,
    locale: response.headers.get("X-Banner-Locale") ?? locale,
  };
}
