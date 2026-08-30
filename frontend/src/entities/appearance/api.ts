import { apiDelete, apiGet, apiPut, apiUpload, BASE_URL } from "@shared/api/http";

export type AppearanceImageKind = "logo" | "favicon";

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
export function getAppearance(): Promise<AppearanceSettings> {
  return apiGet<AppearanceSettings>("/appearance");
}

export function updateAppearance(payload: UpdateAppearancePayload): Promise<AppearanceSettings> {
  return apiPut<AppearanceSettings, UpdateAppearancePayload>("/settings/appearance", payload);
}

// Clears brand_name/primary_color back to unset -- unlike updateAppearance,
// which only ever writes fields it's given (undefined means "don't touch"),
// this is the only way to explicitly revert them to the default.
export function resetAppearanceSettings(): Promise<AppearanceSettings> {
  return apiDelete<AppearanceSettings>("/settings/appearance");
}

export function uploadAppearanceImage(
  kind: AppearanceImageKind,
  file: File,
): Promise<AppearanceSettings> {
  const formData = new FormData();
  formData.append("file", file);
  return apiUpload<AppearanceSettings>(`/settings/appearance/${kind}`, formData);
}

export function deleteAppearanceImage(kind: AppearanceImageKind): Promise<null> {
  return apiDelete<null>(`/settings/appearance/${kind}`);
}

// Public image endpoints -- unlike banners, these need no Authorization header,
// so a plain <img src> works directly (no blob-fetch dance).
export function appearanceImageUrl(kind: AppearanceImageKind): string {
  return `${BASE_URL}/appearance/${kind}`;
}
