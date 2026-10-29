import { apiDelete, apiGet, apiPatch, apiPost, apiUpload, BASE_URL } from "@shared/api/http";

export type AppearanceImageKind = "logo" | "favicon";

export type AppearanceTarget = "dashboard" | "cabinet";

export const DEFAULT_FAVICON_HREF = "/favicon.svg";

export interface AppearanceSettings {
  brand_name: string | null;
  primary_color: string | null;
  shader_palette: string[] | null;
  shader_enabled: boolean;
  has_logo: boolean;
  has_favicon: boolean;
}

export interface UpdateAppearancePayload {
  brand_name?: string;
  primary_color?: string;
  shader_palette?: string[];
  shader_enabled?: boolean;
}

// public endpoint, the pre-login LoginPage reads it too
export function getAppearance(target: AppearanceTarget, signal?: AbortSignal): Promise<AppearanceSettings> {
  return apiGet<AppearanceSettings>(`/appearance/${target}`, signal);
}

export function updateAppearance(
  target: AppearanceTarget,
  payload: UpdateAppearancePayload,
): Promise<AppearanceSettings> {
  return apiPatch<AppearanceSettings, UpdateAppearancePayload>(`/settings/appearance/${target}`, payload);
}

// Clears every field back to the default; updateAppearance skips undefined
// fields and can't. Images are separate: deleteAppearanceImage.
export function resetAppearanceSettings(target: AppearanceTarget): Promise<AppearanceSettings> {
  return apiPost<AppearanceSettings, Record<string, never>>(`/settings/appearance/${target}/actions/reset`, {});
}

// bumped on every upload/delete: the image URLs never change, so a replaced
// logo/favicon would keep coming from the browser cache
let imageVersion = Date.now();

export async function uploadAppearanceImage(
  target: AppearanceTarget,
  kind: AppearanceImageKind,
  file: File,
): Promise<AppearanceSettings> {
  const formData = new FormData();
  formData.append("file", file);
  const result = await apiUpload<AppearanceSettings>(`/settings/appearance/${target}/${kind}`, formData);
  imageVersion = Date.now();
  return result;
}

export async function deleteAppearanceImage(
  target: AppearanceTarget,
  kind: AppearanceImageKind,
): Promise<AppearanceSettings> {
  const result = await apiDelete<AppearanceSettings>(`/settings/appearance/${target}/${kind}`);
  imageVersion = Date.now();
  return result;
}

// public image endpoints: unlike banners no Authorization header, so a plain
// <img src> works
export function appearanceImageUrl(target: AppearanceTarget, kind: AppearanceImageKind): string {
  return `${BASE_URL}/appearance/${target}/${kind}?v=${imageVersion}`;
}
