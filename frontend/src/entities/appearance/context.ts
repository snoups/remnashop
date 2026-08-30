import { createContext } from "react";

import type { AppearanceSettings } from "@entities/appearance/api";
import type { AsyncState } from "@shared/lib/use-async-resource";

export const AppearanceContext = createContext<AsyncState<AppearanceSettings> | null>(null);
export const AppearanceReloadContext = createContext<(() => void) | null>(null);

export interface AppearancePreview {
  previewColor: string | null;
  setPreviewColor: (color: string | null) => void;
  previewPalette: string[] | null;
  setPreviewPalette: (palette: string[] | null) => void;
  previewShaderEnabled: boolean | null;
  setPreviewShaderEnabled: (enabled: boolean | null) => void;
}

// Lets the Appearance settings form preview an accent color pick across the
// whole dashboard (CSS tokens + shader hue) before it's saved -- separate
// from AppearanceContext, which only ever reflects the last value confirmed
// by the backend.
export const AppearancePreviewContext = createContext<AppearancePreview | null>(null);
