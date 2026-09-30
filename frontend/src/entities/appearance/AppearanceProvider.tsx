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

// Reverting an admin's chosen accent color has to actively clear the inline
// override, not just skip setting a new one -- these are set via inline
// style, which wins the cascade over styles.css's @theme defaults until
// explicitly removed.
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

// Fill baked into public/favicon.svg. A tab icon is its own document, so
// --color-primary can't reach it -- recolor by rewriting the SVG instead.
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
  // Set by the Appearance settings form while the admin is trying out a
  // color, before saving. Takes priority over the fetched value everywhere
  // this provider applies color -- null means "no live preview," fall back
  // to whatever the backend last confirmed.
  const [previewColor, setPreviewColor] = useState<string | null>(null);
  const effectiveColor = previewColor ?? (state.kind === "ready" ? state.data.primary_color : null);
  // Same live-preview mechanism as previewColor, but for the shader's raw
  // palette -- only ShaderBackground reads this (via useEffectiveShaderPalette),
  // not applyTheme, so no CSS side effect here.
  const [previewPalette, setPreviewPalette] = useState<string[] | null>(null);
  // Same idea, for the shader on/off toggle.
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
