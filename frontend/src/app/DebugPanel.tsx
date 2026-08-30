import { Leva, button, useControls } from "leva";
import { useEffect } from "react";

import { PALETTE, shaderDebugState, DEFAULT_TIME_SCALE } from "@app/shaderState";
import { DEFAULT_BOUNCE_STRENGTH, setBounceStrength } from "@shared/lib/bounceState";

type Rgba = { r: number; g: number; b: number; a: number };

function vector3ToHex(v: { x: number; y: number; z: number }): string {
  const toHex = (n: number) => Math.round(Math.min(1, Math.max(0, n)) * 255).toString(16).padStart(2, "0");
  return `#${toHex(v.x)}${toHex(v.y)}${toHex(v.z)}`;
}

function hexToRgba(hex: string): Rgba {
  const clean = hex.replace("#", "");
  return {
    r: parseInt(clean.slice(0, 2), 16),
    g: parseInt(clean.slice(2, 4), 16),
    b: parseInt(clean.slice(4, 6), 16),
    a: clean.length >= 8 ? parseInt(clean.slice(6, 8), 16) / 255 : 1,
  };
}

function rgbaToHex({ r, g, b, a }: Rgba): string {
  const toHex = (n: number) => Math.round(n).toString(16).padStart(2, "0");
  const base = `#${toHex(r)}${toHex(g)}${toHex(b)}`;
  return a >= 1 ? base : `${base}${toHex(a * 255)}`;
}

// key: [CSS custom property name, default hex/8-digit-hex from styles.css]
// --color-primary/-primary-hover/-accent/-accent-foreground are deliberately
// NOT here -- those 4 are owned by AppearanceProvider (derived from the
// admin's configured accent color, fetched from the backend), not by this
// panel's hardcoded design-system defaults. Keeping them here raced the two
// writers on every mount/reload, with whichever fired last silently
// overwriting the other's value on the page.
const CSS_COLOR_TOKENS = [
  ["canvas", "--color-canvas", "#111111"],
  ["input", "--color-input", "#121212d6"],
  ["surface", "--color-surface", "#393c47"],
  ["popover", "--color-popover", "#393c47"],
  ["border", "--color-border", "#e8ecfb17"],
  ["glassBorder", "--color-glass-border", "#e8ecfb17"],
  ["foreground", "--color-foreground", "#e8ecfb"],
  ["mutedForeground", "--color-muted-foreground", "#8b93b8"],
  ["primaryForeground", "--color-primary-foreground", "#01030f"],
  ["success", "--color-success", "#00c758"],
  ["warning", "--color-warning", "#f99c00"],
  ["error", "--color-error", "#fb2c36"],
] as const;

// key: [CSS custom property name, default px from styles.css]
const RADIUS_TOKENS = [
  ["popover", "--radius-popover", 20],
  ["popoverItem", "--radius-popover-item", 14],
  ["dialog", "--radius-dialog", 24],
] as const;

const RADIUS_DEFAULTS: Record<string, number> = Object.fromEntries(
  RADIUS_TOKENS.map(([key, , defaultPx]) => [key, defaultPx]),
);

const SHADER_DEFAULTS = {
  opacity: PALETTE.opacity,
  speed: DEFAULT_TIME_SCALE,
  uvScale: 1,
  distortionIterations: 3,
  distortionIntensity: 0.15,
};

// See the comment on the "Palette (a/b/c/d)" folder below for why these vec3
// uniforms are exposed as colour swatches.
const PALETTE_DEFAULTS = {
  base: vector3ToHex(PALETTE.colours[0]),
  amplitude: vector3ToHex(PALETTE.colours[1]),
  frequency: vector3ToHex(PALETTE.colours[2]),
  phase: vector3ToHex(PALETTE.colours[3]),
};

const CSS_DEFAULTS: Record<string, Rgba> = Object.fromEntries(
  CSS_COLOR_TOKENS.map(([key, , defaultHex]) => [key, hexToRgba(defaultHex)]),
);

/**
 * Dev-only tweak panel (leva) for the shader's uniforms and the app's CSS
 * colour tokens. Never mounted in production — App.tsx only renders this
 * behind `import.meta.env.DEV`, which Vite statically replaces with `false`
 * and strips from the prod bundle, taking `leva` with it.
 */
export function DebugPanel() {
  const [shaderValues, setShaderValues] = useControls("Shader", () => ({
    opacity: { value: SHADER_DEFAULTS.opacity, min: 0, max: 1 },
    speed: { value: SHADER_DEFAULTS.speed, min: 0, max: 2 },
    uvScale: { value: SHADER_DEFAULTS.uvScale, min: 0.1, max: 5 },
    distortionIterations: { value: SHADER_DEFAULTS.distortionIterations, min: 0, max: 8, step: 1 },
    distortionIntensity: { value: SHADER_DEFAULTS.distortionIntensity, min: 0, max: 1 },
  }));

  // The four vec3 uniforms aren't literally colours — they're the a/b/c/d
  // coefficients of a cosine-gradient palette (a + b*cos(2π(c*t+d))) — but
  // editing each as an RGB swatch is the standard way to tweak this exact
  // technique (see iq's "Palettes" article), and it's what actually renders
  // when the swatches happen to already sit in the 0..1 range, as these do.
  const [paletteValues, setPaletteValues] = useControls("Palette (a/b/c/d)", () => ({ ...PALETTE_DEFAULTS }));

  const [cssValues, setCssValues] = useControls("CSS tokens", () => ({ ...CSS_DEFAULTS }));

  const [radiusValues, setRadiusValues] = useControls("Radius", () =>
    Object.fromEntries(RADIUS_TOKENS.map(([key, , defaultPx]) => [key, { value: defaultPx, min: 0, max: 40, step: 1 }])),
  );

  const [{ strength: bounceStrength }, setBounce] = useControls("Bounce", () => ({
    strength: { value: DEFAULT_BOUNCE_STRENGTH, min: 0, max: 2 },
  }));

  // Per-field reset buttons — appended into each folder above (leva merges
  // multiple useControls() calls sharing the same folder name into one).
  useControls("Shader", () => ({
    "↺ opacity": button(() => setShaderValues({ opacity: SHADER_DEFAULTS.opacity })),
    "↺ speed": button(() => setShaderValues({ speed: SHADER_DEFAULTS.speed })),
    "↺ uvScale": button(() => setShaderValues({ uvScale: SHADER_DEFAULTS.uvScale })),
    "↺ distortionIterations": button(() =>
      setShaderValues({ distortionIterations: SHADER_DEFAULTS.distortionIterations }),
    ),
    "↺ distortionIntensity": button(() =>
      setShaderValues({ distortionIntensity: SHADER_DEFAULTS.distortionIntensity }),
    ),
  }));

  useControls("Palette (a/b/c/d)", () => ({
    "↺ base": button(() => setPaletteValues({ base: PALETTE_DEFAULTS.base })),
    "↺ amplitude": button(() => setPaletteValues({ amplitude: PALETTE_DEFAULTS.amplitude })),
    "↺ frequency": button(() => setPaletteValues({ frequency: PALETTE_DEFAULTS.frequency })),
    "↺ phase": button(() => setPaletteValues({ phase: PALETTE_DEFAULTS.phase })),
  }));

  useControls("CSS tokens", () =>
    Object.fromEntries(
      CSS_COLOR_TOKENS.map(([key]) => [`↺ ${key}`, button(() => setCssValues({ [key]: CSS_DEFAULTS[key] }))]),
    ),
  );

  useControls("Radius", () =>
    Object.fromEntries(
      RADIUS_TOKENS.map(([key]) => [`↺ ${key}`, button(() => setRadiusValues({ [key]: RADIUS_DEFAULTS[key] }))]),
    ),
  );

  useControls("Bounce", () => ({
    "↺ strength": button(() => setBounce({ strength: DEFAULT_BOUNCE_STRENGTH })),
  }));

  useControls("Export", {
    "Copy values": button(() => {
      void navigator.clipboard.writeText(buildExportText(shaderValues, paletteValues, cssValues, radiusValues));
    }),
    "Reset all": button(() => {
      setShaderValues(SHADER_DEFAULTS);
      setPaletteValues(PALETTE_DEFAULTS);
      setCssValues(CSS_DEFAULTS);
      setRadiusValues(RADIUS_DEFAULTS);
      setBounce({ strength: DEFAULT_BOUNCE_STRENGTH });
    }),
  });

  useEffect(() => {
    setBounceStrength(bounceStrength);
  }, [bounceStrength]);

  useEffect(() => {
    const uniforms = shaderDebugState.uniforms;
    if (!uniforms) return;
    uniforms.uOpacity.value = shaderValues.opacity;
    uniforms.uUvScale.value = shaderValues.uvScale;
    uniforms.uUvDistortionIterations.value = shaderValues.distortionIterations;
    uniforms.uUvDistortionIntensity.value = shaderValues.distortionIntensity;
    shaderDebugState.speed = shaderValues.speed;
  }, [shaderValues]);

  useEffect(() => {
    const uniforms = shaderDebugState.uniforms;
    if (!uniforms) return;
    const hexes = [paletteValues.base, paletteValues.amplitude, paletteValues.frequency, paletteValues.phase];
    hexes.forEach((hex, i) => {
      const { r, g, b } = hexToRgba(hex);
      uniforms.uColourPalette.value[i]!.set(r / 255, g / 255, b / 255);
    });
  }, [paletteValues]);

  useEffect(() => {
    for (const [key, cssVar] of CSS_COLOR_TOKENS) {
      document.documentElement.style.setProperty(cssVar, rgbaToHex(cssValues[key]!));
    }
  }, [cssValues]);

  useEffect(() => {
    for (const [key, cssVar] of RADIUS_TOKENS) {
      document.documentElement.style.setProperty(cssVar, `${radiusValues[key]}px`);
    }
  }, [radiusValues]);

  return (
    <Leva
      collapsed
      titleBar={{ title: "Design tweaks" }}
      theme={{ sizes: { rootWidth: "380px", controlWidth: "180px" } }}
    />
  );
}

function buildExportText(
  shaderValues: { opacity: number; speed: number; uvScale: number; distortionIterations: number; distortionIntensity: number },
  paletteValues: { base: string; amplitude: string; frequency: string; phase: string },
  cssValues: Record<string, Rgba>,
  radiusValues: Record<string, number>,
): string {
  const vec3Line = (hex: string) => {
    const { r, g, b } = hexToRgba(hex);
    return `new THREE.Vector3(${(r / 255).toFixed(3)}, ${(g / 255).toFixed(3)}, ${(b / 255).toFixed(3)}),`;
  };

  const shaderBlock = [
    "// Paste into src/app/ShaderBackground.tsx",
    "export const PALETTE = {",
    `  opacity: ${shaderValues.opacity.toFixed(3)},`,
    "  colours: [",
    `    ${vec3Line(paletteValues.base)}`,
    `    ${vec3Line(paletteValues.amplitude)}`,
    `    ${vec3Line(paletteValues.frequency)}`,
    `    ${vec3Line(paletteValues.phase)}`,
    "  ] as [THREE.Vector3, THREE.Vector3, THREE.Vector3, THREE.Vector3],",
    "};",
    `export const DEFAULT_TIME_SCALE = ${shaderValues.speed.toFixed(3)};`,
    "// uUvScale default:",
    `${shaderValues.uvScale.toFixed(3)}`,
    "// uUvDistortionIterations default:",
    `${shaderValues.distortionIterations}`,
    "// uUvDistortionIntensity default:",
    `${shaderValues.distortionIntensity.toFixed(3)}`,
  ].join("\n");

  const cssBlock = [
    "",
    "/* Paste into src/app/styles.css's @theme block */",
    ...CSS_COLOR_TOKENS.map(([key, cssVar]) => `${cssVar}: ${rgbaToHex(cssValues[key]!)};`),
    ...RADIUS_TOKENS.map(([key, cssVar]) => `${cssVar}: ${radiusValues[key]}px;`),
  ].join("\n");

  return `${shaderBlock}\n${cssBlock}`;
}
