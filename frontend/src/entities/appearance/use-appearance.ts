import { useContext } from "react";

import type { AppearanceSettings } from "@entities/appearance/api";
import type { AsyncState } from "@shared/lib/use-async-resource";

import { AppearanceContext, AppearancePreviewContext, AppearanceReloadContext, type AppearancePreview } from "./context";

export const DEFAULT_BRAND_NAME = "Remnashop";

export function useAppearance(): AsyncState<AppearanceSettings> {
  const state = useContext(AppearanceContext);
  if (state === null) {
    throw new Error("useAppearance must be used within an AppearanceProvider");
  }
  return state;
}

export function useReloadAppearance(): () => void {
  const reload = useContext(AppearanceReloadContext);
  if (reload === null) {
    throw new Error("useReloadAppearance must be used within an AppearanceProvider");
  }
  return reload;
}

export function useBrandName(): string {
  const state = useAppearance();
  return state.kind === "ready" ? (state.data.brand_name ?? DEFAULT_BRAND_NAME) : DEFAULT_BRAND_NAME;
}

export function useAppearancePreview(): AppearancePreview {
  const value = useContext(AppearancePreviewContext);
  if (value === null) {
    throw new Error("useAppearancePreview must be used within an AppearanceProvider");
  }
  return value;
}

// The color to actually render with right now: a live, unsaved preview from
// the settings form if one is set, otherwise whatever the backend last
// confirmed. Anything that paints the accent color (the shader, in
// particular) should read this instead of useAppearance()'s raw fetched
// value, so a preview-in-progress shows up everywhere consistently.
export function useEffectiveAccentColor(): string | null {
  const state = useAppearance();
  const { previewColor } = useAppearancePreview();
  return previewColor ?? (state.kind === "ready" ? state.data.primary_color : null);
}

// Same idea as useEffectiveAccentColor, for the shader's raw palette override.
// null means "no admin override, no live preview" -- callers fall back to
// the shader's own hardcoded default (app/shaderState.ts's
// DEFAULT_SHADER_PALETTE_HEX), which this entities-layer hook doesn't know
// about.
export function useEffectiveShaderPalette(): string[] | null {
  const state = useAppearance();
  const { previewPalette } = useAppearancePreview();
  return previewPalette ?? (state.kind === "ready" ? state.data.shader_palette : null);
}

// Same idea, for the shader's on/off toggle. Defaults to true while loading
// or unset, matching the backend's own default.
export function useEffectiveShaderEnabled(): boolean {
  const state = useAppearance();
  const { previewShaderEnabled } = useAppearancePreview();
  return previewShaderEnabled ?? (state.kind === "ready" ? state.data.shader_enabled : true);
}
