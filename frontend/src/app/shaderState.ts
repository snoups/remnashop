import { DEFAULT_SHADER_PALETTE_HEX, hexToRgbNormalized, hueRotationCoefficients } from "@shared/lib/color";

// Opaque canvas (alpha: false), so opacity is a brightness multiplier, not a blend.
// colours: flat rgb triplets, the layout gl.uniform3fv expects for a vec3[4].
export const PALETTE = {
  opacity: 0.5,
  colours: DEFAULT_SHADER_PALETTE_HEX.flatMap((hex) => hexToRgbNormalized(hex)),
};

// uTime at wall-clock speed reads as jittery; slows the motion without touching the noise math
export const DEFAULT_TIME_SCALE = 0.2;

export type ShaderUniforms = {
  uTime: { value: number };
  uTimeSin: { value: number };
  uScrollProgress: { value: number };
  uOpacity: { value: number };
  uColourPalette: { value: Float32Array };
  uUvScale: { value: number };
  uUvDistortionIterations: { value: number };
  uUvDistortionIntensity: { value: number };
  uHueRotationMatrix: { value: Float32Array };
};

// The accent color rotates the gradient's hue by its delta from DEFAULT_ACCENT_COLOR.
// Built once per angle change, not per fragment: the same 9 values for every pixel.
// Row-major, uploaded with transpose=true.
export function buildHueRotationMatrix(angleRadians: number): Float32Array {
  return Float32Array.from(hueRotationCoefficients(angleRadians));
}
