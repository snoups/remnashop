import { hexToRgbNormalized, hueRotationCoefficients } from "@shared/lib/color";

// Opaque canvas (alpha: false), so opacity is a brightness multiplier, not a blend.
export const SHADER_GRADIENT_OPACITY = 0.5;
// a moment of the animation whose colours spread well across a still frame
const STILL_TIME = 4;

// One oversized triangle over the viewport, generated from gl_VertexID; no vertex buffer.
const VERTEX_SHADER = `#version 300 es
out vec2 vUv;

void main() {
  vec2 position = vec2(gl_VertexID == 1 ? 3.0 : -1.0, gl_VertexID == 2 ? 3.0 : -1.0);
  vUv = position * 0.5 + 0.5;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

uniform float uTime;
uniform float uTimeSin;
uniform float uScrollProgress;
uniform float uOpacity;
uniform vec3 uColourPalette[4];
uniform float uUvScale;
uniform float uUvDistortionIterations;
uniform float uUvDistortionIntensity;
uniform mat3 uHueRotationMatrix;

in vec2 vUv;
out vec4 fragColor;

vec3 mod289(vec3 x) {
  return x - floor(x * (1.0 / 289.0)) * 289.0;
}

vec4 mod289(vec4 x) {
  return x - floor(x * (1.0 / 289.0)) * 289.0;
}

vec4 permute(vec4 x) {
  return mod289(((x * 34.0) + 1.0) * x);
}

vec4 taylorInvSqrt(vec4 r) {
  return 1.79284291400159 - 0.85373472095314 * r;
}

float snoise(vec3 v) {
  const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);

  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);

  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);

  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;

  i = mod289(i);
  vec4 p = permute(permute(permute(
    i.z + vec4(0.0, i1.z, i2.z, 1.0))
    + i.y + vec4(0.0, i1.y, i2.y, 1.0))
    + i.x + vec4(0.0, i1.x, i2.x, 1.0));

  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;

  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);

  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);

  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);

  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);

  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));

  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;

  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);

  vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
  p0 *= norm.x;
  p1 *= norm.y;
  p2 *= norm.z;
  p3 *= norm.w;

  vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}

vec3 cosineGradientColour(in float t, in vec3 a, in vec3 b, in vec3 c, in vec3 d) {
  return clamp(a + b * cos(6.28318 * (c * t + d)), 0.0, 1.0);
}

void main() {
  vec2 uv = vUv;
  uv.x += uScrollProgress;
  uv *= uUvScale;
  uv.x /= 1.2;

  for (float i = 0.0; i < uUvDistortionIterations; i++) {
    uv += snoise(vec3(uv - i * 0.2, uTime + i * 32.0)) * uUvDistortionIntensity;
  }

  float colourInput = snoise(vec3(uv, uTimeSin)) * 0.5 + 0.5;
  vec3 colour = cosineGradientColour(colourInput, uColourPalette[0], uColourPalette[1], uColourPalette[2], uColourPalette[3]);
  colour = uHueRotationMatrix * colour;
  fragColor = vec4(colour * 1.4 * uOpacity, uOpacity);
}
`;

/** The app background's noise gradient (ShaderBackground), compiled on `gl`; null when linking fails. */
export function compileShaderGradient(gl: WebGL2RenderingContext): WebGLProgram | null {
  const program = gl.createProgram();
  for (const [type, source] of [
    [gl.VERTEX_SHADER, VERTEX_SHADER],
    [gl.FRAGMENT_SHADER, FRAGMENT_SHADER],
  ] as const) {
    const shader = gl.createShader(type)!;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    gl.attachShader(program, shader);
    gl.deleteShader(shader); // only flagged, freed with the program
  }
  gl.linkProgram(program);
  if (gl.getProgramParameter(program, gl.LINK_STATUS)) return program;
  console.error("shader-gradient: link failed", gl.getProgramInfoLog(program));
  gl.deleteProgram(program);
  return null;
}


/** One still frame of the background's gradient as a PNG data URL, for a surface a snapshot has to see
 *  (the live background is a WebGL canvas behind everything). null without WebGL2. */
export function renderShaderGradientImage({
  width,
  height,
  palette,
  hueRadians,
}: {
  width: number;
  height: number;
  /** four hex colours, the gradient's cosine-palette terms */
  palette: string[];
  hueRadians: number;
}): string | null {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true, alpha: false });
  if (!gl || gl.isContextLost()) return null;
  const program = compileShaderGradient(gl);
  if (!program) return null;
  gl.useProgram(program);
  gl.viewport(0, 0, width, height);
  const set = (name: string, apply: (location: WebGLUniformLocation | null) => void) =>
    apply(gl.getUniformLocation(program, name));
  set("uTime", (l) => gl.uniform1f(l, STILL_TIME));
  set("uTimeSin", (l) => gl.uniform1f(l, Math.sin(STILL_TIME)));
  set("uScrollProgress", (l) => gl.uniform1f(l, 0));
  set("uOpacity", (l) => gl.uniform1f(l, SHADER_GRADIENT_OPACITY));
  set("uColourPalette", (l) => gl.uniform3fv(l, Float32Array.from(palette.flatMap((hex) => hexToRgbNormalized(hex)))));
  set("uUvScale", (l) => gl.uniform1f(l, 1));
  set("uUvDistortionIterations", (l) => gl.uniform1f(l, 3));
  set("uUvDistortionIntensity", (l) => gl.uniform1f(l, 0.15));
  set("uHueRotationMatrix", (l) => gl.uniformMatrix3fv(l, true, Float32Array.from(hueRotationCoefficients(hueRadians))));
  gl.drawArrays(gl.TRIANGLES, 0, 3);
  const url = canvas.toDataURL("image/png");
  gl.deleteProgram(program);
  // a throwaway canvas: give its context back now rather than at garbage collection
  gl.getExtension("WEBGL_lose_context")?.loseContext();
  return url;
}
