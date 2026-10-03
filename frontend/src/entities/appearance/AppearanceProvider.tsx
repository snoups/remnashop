import { useEffect, useState, type ReactNode } from "react";

import { appearanceImageUrl, DEFAULT_FAVICON_HREF, getAppearance } from "@entities/appearance/api";
import { deriveTheme } from "@shared/lib/color";
import { useAsyncResource } from "@shared/lib/use-async-resource";

import { AppearanceContext, AppearancePreviewContext, AppearanceReloadContext } from "./context";

const THEME_CSS_PROPERTIES = [
  "--color-primary",
  "--color-primary-foreground",
  "--color-primary-hover",
  "--color-accent",
  "--color-accent-foreground",
] as const;

// inline styles beat styles.css's @theme defaults, so a revert has to remove them
function applyTheme(primaryColor: string | null) {
  const root = document.documentElement.style;
  if (!primaryColor) {
    for (const property of THEME_CSS_PROPERTIES) root.removeProperty(property);
    return;
  }

  const theme = deriveTheme(primaryColor);
  root.setProperty("--color-primary", theme.primary);
  root.setProperty("--color-primary-foreground", theme.primaryForeground);
  root.setProperty("--color-primary-hover", theme.primaryHover);
  root.setProperty("--color-accent", theme.accent);
  root.setProperty("--color-accent-foreground", theme.accentForeground);
}

// Fill baked into public/favicon.svg. A tab icon is its own document that
// --color-primary can't reach, so the SVG itself is rewritten.
const DEFAULT_FAVICON_COLOR = "#22D3EE";
let defaultFaviconSvg: Promise<string> | null = null;

async function defaultFaviconHref(color: string | null): Promise<string> {
  if (!color) return DEFAULT_FAVICON_HREF;
  defaultFaviconSvg ??= fetch(DEFAULT_FAVICON_HREF).then((response) => response.text());
  const svg = (await defaultFaviconSvg).replaceAll(DEFAULT_FAVICON_COLOR, color);
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [state, reload] = useAsyncResource(getAppearance);
  // unsaved picks from the Appearance settings form; null falls back to the fetched value
  const [previewColor, setPreviewColor] = useState<string | null>(null);
  const effectiveColor = previewColor ?? (state.kind === "ready" ? state.data.primary_color : null);
  const [previewPalette, setPreviewPalette] = useState<string[] | null>(null);
  const [previewShaderEnabled, setPreviewShaderEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    applyTheme(effectiveColor);
  }, [effectiveColor]);

  useEffect(() => {
    if (state.kind !== "ready") return;
    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (!link) return;
    if (state.data.has_favicon) {
      link.href = appearanceImageUrl("favicon");
      return;
    }
    // guards against a slower earlier color resolving after a newer one
    let isStale = false;
    defaultFaviconHref(effectiveColor)
      .then((href) => {
        if (!isStale) link.href = href;
      })
      .catch(() => {
        defaultFaviconSvg = null;
      });
    return () => {
      isStale = true;
    };
  }, [state, effectiveColor]);

  return (
    <AppearanceContext.Provider value={state}>
      <AppearanceReloadContext.Provider value={reload}>
        <AppearancePreviewContext.Provider
          value={{
            previewColor,
            setPreviewColor,
            previewPalette,
            setPreviewPalette,
            previewShaderEnabled,
            setPreviewShaderEnabled,
          }}
        >
          {children}
        </AppearancePreviewContext.Provider>
      </AppearanceReloadContext.Provider>
    </AppearanceContext.Provider>
  );
}
