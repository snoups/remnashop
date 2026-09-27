import { apiDelete, apiGet, apiPut, apiUpload, BASE_URL } from "@shared/api/http";

export type AppearanceImageKind = "logo" | "favicon";

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

// Public endpoint, no auth required -- readable from the pre-login LoginPage too.
export function getAppearance(signal?: AbortSignal): Promise<AppearanceSettings> {
  return apiGet<AppearanceSettings>("/appearance", signal);
}

export function updateAppearance(payload: UpdateAppearancePayload): Promise<AppearanceSettings> {
  return apiPut<AppearanceSettings, UpdateAppearancePayload>("/settings/appearance", payload);
}

export type AppearanceResetScope = "branding" | "colors";

// Clears one scope's fields back to unset -- unlike updateAppearance, which
// only ever writes fields it's given (undefined means "don't touch"), this is
// the only way to explicitly revert them to the default. Images are separate:
// deleteAppearanceImage.
export function resetAppearanceSettings(scope: AppearanceResetScope): Promise<AppearanceSettings> {
  return apiDelete<AppearanceSettings>(`/settings/appearance?scope=${scope}`);
}

// Image URLs never change on their own, so a replaced logo/favicon would keep
// rendering from the browser cache -- bumped on every upload/delete.
let imageVersion = Date.now();

export async function uploadAppearanceImage(
  kind: AppearanceImageKind,
  file: File,
): Promise<AppearanceSettings> {
  const formData = new FormData();
  formData.append("file", file);
  const result = await apiUpload<AppearanceSettings>(`/settings/appearance/${kind}`, formData);
  imageVersion = Date.now();
  return result;
}

export async function deleteAppearanceImage(kind: AppearanceImageKind): Promise<null> {
  const result = await apiDelete<null>(`/settings/appearance/${kind}`);
  imageVersion = Date.now();
  return result;
}

// Public image endpoints -- unlike banners, these need no Authorization header,
// so a plain <img src> works directly (no blob-fetch dance).
export function appearanceImageUrl(kind: AppearanceImageKind): string {
  return `${BASE_URL}/appearance/${kind}?v=${imageVersion}`;
}
