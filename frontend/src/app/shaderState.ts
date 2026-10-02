import { DEFAULT_SHADER_PALETTE_HEX, hexToRgbNormalized, hueRotationCoefficients } from "@shared/lib/color";

// The renderer is opaque (alpha: false) — the canvas IS the page background,
// there is no DOM colour behind it to blend with. So opacity is just a
// brightness multiplier, not a blend-with-background knob.
//
// colours is derived from shared/lib/color.ts's DEFAULT_SHADER_PALETTE_HEX
// (the single source of truth, also used by the Appearance settings form's
// default swatches) rather than hardcoding its own numbers. Flat rgb triplets,
// the layout gl.uniform3fv expects for a vec3[4].
export const PALETTE = {
  opacity: 0.5,
  colours: DEFAULT_SHADER_PALETTE_HEX.flatMap((hex) => hexToRgbNormalized(hex)),
};

// uTime feeds the noise functions almost directly, so 1:1 with wall-clock
// seconds reads as fast, jittery motion. Scaling it down slows the animation
// without touching the noise/distortion math itself.
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

// The dashboard's admin-configured accent color doesn't replace or mix into
// the shader's native palette directly -- it rotates the whole rendered
// gradient's hue by the delta between the picked color and
// shared/lib/color.ts's DEFAULT_ACCENT_COLOR (the reference point the native
// palette was designed against).
//
// The rotation matrix (same one behind CSS's filter: hue-rotate()) is built
// here, once, whenever the angle changes -- not in the shader. It's the same
// 9 values for every pixel in a frame, so computing it per-fragment (as an
// earlier version of this did) redoes identical trig and arithmetic millions
// of times a frame for no benefit; the shader just multiplies each pixel's
// colour by this precomputed matrix. Row-major -- uploaded with transpose=true.
export function buildHueRotationMatrix(angleRadians: number): Float32Array {
  return Float32Array.from(hueRotationCoefficients(angleRadians));
}
