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

export function restoreDefaultBanner(): Promise<null> {
  return apiPost<null, Record<string, never>>("/banners/actions/reset-default", {});
}

export function deleteBanner(name: string, locale: string): Promise<null> {
  return apiDelete<null>(`/banners/${name}/${locale}`);
}

export async function fetchBannerImageBlob(name: string, locale: string, signal?: AbortSignal): Promise<Blob> {
  return (await apiGetRaw(`/banners/${name}/${locale}/image`, signal)).blob();
}
