function hexToRgb(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ];
}

// 0..1 range, for feeding a hex color into a WebGL uniform.
export function hexToRgbNormalized(hex: string): [number, number, number] {
  const [r, g, b] = hexToRgb(hex);
  return [r / 255, g / 255, b / 255];
}

// The shader's default cosine-gradient palette (base/amplitude/frequency/
// phase), in hex -- source of truth for both app/shaderState.ts's Vector3
// uniforms and the Appearance settings form's default swatches. Lives here,
// not in app/shaderState.ts, so features/entities-layer code can read it
// without reaching upward into the app layer (FSD).
export const DEFAULT_SHADER_PALETTE_HEX: readonly [string, string, string, string] = [
  "#0f1629",
  "#050d0d",
  "#ffffff",
  "#998066",
];

function rgbToHex(r: number, g: number, b: number): string {
  const toHex = (channel: number) => Math.round(channel).toString(16).padStart(2, "0");
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function mixWithWhite(hex: string, ratio: number): string {
  const [r, g, b] = hexToRgb(hex);
  return rgbToHex(r + (255 - r) * ratio, g + (255 - g) * ratio, b + (255 - b) * ratio);
}

function shade(hex: string, ratio: number): string {
  const [r, g, b] = hexToRgb(hex);
  return rgbToHex(r * (1 - ratio), g * (1 - ratio), b * (1 - ratio));
}

// WCAG relative luminance / contrast ratio
function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map((channel) => {
    const c = channel / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

const MIN_TEXT_CONTRAST = 4.5;

// dark tint of the accent itself, so solid-button text stays in its hue;
// white where the tint can't reach AA (indigo, custom dark accents)
function primaryForeground(primaryColor: string): string {
  const tint = shade(primaryColor, 0.85);
  const tintContrast = contrastRatio(primaryColor, tint);
  if (tintContrast >= MIN_TEXT_CONTRAST) return tint;
  return contrastRatio(primaryColor, "#ffffff") > tintContrast ? "#ffffff" : tint;
}

// The form's blank-state placeholder and the shader's reference color --
// ShaderBackground rotates its native palette's hue by the delta between the
// admin's picked accent and this value, so this is the anchor "no rotation"
// point, not an arbitrary default.
export const DEFAULT_ACCENT_COLOR = "#22d3ee";

// Degrees, 0..360. Used to compute how far a picked accent color's hue sits
// from DEFAULT_ACCENT_COLOR's, which becomes the shader's hue-rotation angle.
export function hexToHueDegrees(hex: string): number {
  const [r, g, b] = hexToRgbNormalized(hex);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  if (delta === 0) return 0;

  let hue: number;
  if (max === r) hue = ((g - b) / delta) % 6;
  else if (max === g) hue = (b - r) / delta + 2;
  else hue = (r - g) / delta + 4;

  hue *= 60;
  return hue < 0 ? hue + 360 : hue;
}

// Row-major coefficients of the hue-rotation matrix (same technique behind
// CSS's filter: hue-rotate()) -- the one source of truth for both
// app/shaderState.ts's buildHueRotationMatrix (a Float32Array for the GLSL
// uniform) and hueRotateHex below (plain hex math, for previewing that same
// rotation on a swatch outside the canvas).
export function hueRotationCoefficients(
  angleRadians: number,
): [number, number, number, number, number, number, number, number, number] {
  const cosA = Math.cos(angleRadians);
  const sinA = Math.sin(angleRadians);
  return [
    0.213 + cosA * 0.787 - sinA * 0.213,
    0.715 - cosA * 0.715 - sinA * 0.715,
    0.072 - cosA * 0.072 + sinA * 0.928,
    0.213 - cosA * 0.213 + sinA * 0.143,
    0.715 + cosA * 0.285 + sinA * 0.140,
    0.072 - cosA * 0.072 - sinA * 0.283,
    0.213 - cosA * 0.213 - sinA * 0.787,
    0.715 - cosA * 0.715 + sinA * 0.715,
    0.072 + cosA * 0.928 + sinA * 0.072,
  ];
}

// Applies the same hue rotation the shader renders with to a plain hex
// color -- lets the Appearance settings form preview what a shader palette
// swatch will actually look like once the admin's accent color rotates it.
export function hueRotateHex(hex: string, angleRadians: number): string {
  const [r, g, b] = hexToRgbNormalized(hex);
  const [m11, m12, m13, m21, m22, m23, m31, m32, m33] = hueRotationCoefficients(angleRadians);
  const clamp01 = (n: number) => Math.min(1, Math.max(0, n));
  return rgbToHex(
    clamp01(m11 * r + m12 * g + m13 * b) * 255,
    clamp01(m21 * r + m22 * g + m23 * b) * 255,
    clamp01(m31 * r + m32 * g + m33 * b) * 255,
  );
}

export interface DerivedTheme {
  primary: string;
  primaryForeground: string;
  primaryHover: string;
  accent: string;
  accentForeground: string;
}

// Admins pick one accent color; the other tokens styles.css already defines
// (--color-primary-foreground/-hover, --color-accent/-foreground)
// are derived from it so buttons/links/highlights stay coherent.
export function deriveTheme(primaryColor: string): DerivedTheme {
  return {
    primary: primaryColor,
    primaryForeground: primaryForeground(primaryColor),
    primaryHover: mixWithWhite(primaryColor, 0.35),
    accent: `${primaryColor}1f`,
    accentForeground: mixWithWhite(primaryColor, 0.75),
  };
}
