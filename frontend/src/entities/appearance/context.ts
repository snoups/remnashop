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

// unsaved picks from the Appearance settings form; AppearanceContext holds only saved values
export const AppearancePreviewContext = createContext<AppearancePreview | null>(null);
