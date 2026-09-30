import { useEffect, useRef } from "react";
import * as THREE from "three";

import { buildHueRotationMatrix, PALETTE, shaderDebugState, type ShaderUniforms } from "@app/shaderState";
import { DEFAULT_ACCENT_COLOR, DEFAULT_SHADER_PALETTE_HEX, hexToHueDegrees, hexToRgbNormalized } from "@shared/lib/color";
import {
  useEffectiveAccentColor,
  useEffectiveShaderEnabled,
  useEffectiveShaderPalette,
} from "@entities/appearance/use-appearance";

// Intentionally NOT setting glslVersion: THREE.GLSL3 — three.js only injects the
// `#define gl_FragColor pc_fragColor` GLSL ES 300 compatibility shim when
// glslVersion is left at its default. `#version 300 es` itself is added for any
// non-raw ShaderMaterial regardless of that flag, so leaving it default is what
// makes this shader's `varying`/`gl_FragColor` syntax actually compile.
const MIN_FRAME_INTERVAL_MS = 1000 / 30;
const BUFFER_SCALE = 0.5;

const VERTEX_SHADER = `
varying vec2 vUv;

void main() {
  vUv = position.xy * 0.5 + 0.5;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`;

const FRAGMENT_SHADER = `
uniform float uTime;
uniform float uTimeSin;
uniform float uScrollProgress;
uniform float uOpacity;
uniform vec3 uColourPalette[4];
uniform float uUvScale;
uniform float uUvDistortionIterations;
uniform float uUvDistortionIntensity;
uniform mat3 uHueRotationMatrix;

varying vec2 vUv;

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
  gl_FragColor = vec4(colour * 1.4 * uOpacity, uOpacity);
}
`;

/**
 * App-wide animated background: a noise-based gradient rendered on a single
 * full-viewport canvas behind everything. Mounted once at the app root so it
 * survives route changes. Ported from remnashop-cabinet's ShaderBackground,
 * dropped down to a dark-only palette (no theme switching here) and without
 * its panel-clipping machinery (nothing in this app needs the shader
 * restricted to one panel's rect — sidebar and content card both show it as-is).
 */
export function ShaderBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const uniformsRef = useRef<ShaderUniforms | null>(null);
  // Checked inside the render loop below -- toggling this skips the actual
  // draw call (saving the GPU/CPU work) without tearing down and recreating
  // the WebGL context, which the mount-once setup effect below isn't set up
  // to cheaply do.
  const enabledRef = useRef(true);
  const accentColor = useEffectiveAccentColor();
  const shaderPalette = useEffectiveShaderPalette();
  const shaderEnabled = useEffectiveShaderEnabled();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let gl: WebGL2RenderingContext | null;
    try {
      gl = canvas.getContext("webgl2");
    } catch {
      gl = null;
    }
    if (!gl) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const renderer = new THREE.WebGLRenderer({ canvas, context: gl, antialias: false, alpha: false });
    // Half a CSS pixel per buffer pixel, upscaled by the browser: every fragment
    // costs 4 snoise() calls (~400 ALU ops), and a low-frequency gradient that
    // sits under a backdrop-blur has no detail to lose at quarter density.
    // Scaled here, not via setPixelRatio(0.5): three.js floors the buffer but rounds the
    // viewport, so an odd window width left the viewport a pixel wider than the buffer.
    const resize = () =>
      renderer.setSize(Math.ceil(window.innerWidth * BUFFER_SCALE), Math.ceil(window.innerHeight * BUFFER_SCALE), false);
    resize();

    const scene = new THREE.Scene();
    const camera = new THREE.Camera();
    const geometry = new THREE.PlaneGeometry(2, 2);
    const uniforms = {
      uTime: { value: 0 },
      uTimeSin: { value: 0 },
      uScrollProgress: { value: 0 },
      uOpacity: { value: PALETTE.opacity },
      uColourPalette: { value: PALETTE.colours as THREE.Vector3[] },
      uUvScale: { value: 1 },
      uUvDistortionIterations: { value: 3 },
      uUvDistortionIntensity: { value: 0.15 },
      uHueRotationMatrix: { value: new THREE.Matrix3() },
    };
    const material = new THREE.ShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      uniforms,
    });
    scene.add(new THREE.Mesh(geometry, material));

    uniformsRef.current = uniforms;
    shaderDebugState.uniforms = uniforms;

    function renderFrame() {
      renderer.render(scene, camera);
    }
    renderFrame();

    function onResize() {
      resize();
      renderFrame();
    }
    window.addEventListener("resize", onResize);

    function onScroll() {
      uniforms.uScrollProgress.value = window.scrollY * 0.0005;
    }
    window.addEventListener("scroll", onScroll, { passive: true });

    let frame = 0;

    function onContextLost() {
      // Deliberately NOT calling event.preventDefault() -- doing so tells the
      // browser "I will restore this context, wait for webglcontextrestored,"
      // which this code never listens for or acts on. Left uncorrected, that
      // mismatch is what caused Safari to keep cycling lost/restored forever:
      // it kept trying to hand the context back to a page that never actually
      // recovered. Omitting it makes the loss permanent and final -- Safari
      // stops retrying, and this background is decorative enough that a
      // one-time, permanent hide is a perfectly fine failure mode.
      if (!reduceMotion) cancelAnimationFrame(frame);
      // `canvas` is a captured const guaranteed non-null by the early return above,
      // but TS doesn't retain that narrowing across a nested function's closure.
      canvas!.style.display = "none";
    }
    canvas.addEventListener("webglcontextlost", onContextLost, false);

    let start = performance.now();
    let lastDraw = 0;

    function render() {
      const now = performance.now();
      if (!reduceMotion) {
        frame = requestAnimationFrame(render);
      }
      // rAF runs at display refresh — 120Hz on ProMotion — while
      // DEFAULT_TIME_SCALE makes the motion slow enough that 30fps is
      // indistinguishable from it.
      if (now - lastDraw < MIN_FRAME_INTERVAL_MS) return;
      lastDraw = now;
      uniforms.uTime.value = ((now - start) / 1000) * shaderDebugState.speed;
      // Same reason the hue matrix is precomputed in shaderState.ts: one value
      // per frame, not per fragment.
      uniforms.uTimeSin.value = Math.sin(uniforms.uTime.value);
      if (enabledRef.current) renderFrame();
    }
    render();

    // rAF only stops on its own when the tab is hidden, not when the window
    // merely loses focus -- a dashboard sitting on a second monitor keeps
    // paying full GPU cost. `start` absorbs the paused span so uTime stays
    // continuous and the pattern doesn't jump on return.
    let pausedAt = 0;

    function onBlur() {
      if (pausedAt) return;
      pausedAt = performance.now();
      cancelAnimationFrame(frame);
    }

    function onFocus() {
      if (!pausedAt) return;
      start += performance.now() - pausedAt;
      pausedAt = 0;
      render();
    }

    if (!reduceMotion) {
      window.addEventListener("blur", onBlur);
      window.addEventListener("focus", onFocus);
    }

    return () => {
      uniformsRef.current = null;
      shaderDebugState.uniforms = null;
      if (!reduceMotion) cancelAnimationFrame(frame);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onScroll);
      canvas.removeEventListener("webglcontextlost", onContextLost);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      // Deliberately NOT calling gl.getExtension("WEBGL_lose_context")?.loseContext()
      // here: it seemed like the correct cleanup (renderer.dispose() alone
      // doesn't free a context supplied externally via `context:`), but this
      // canvas element is reused across remounts -- both React StrictMode's
      // deliberate dev-only mount/cleanup/remount dance on first render, and
      // Vite HMR/Fast Refresh. Force-losing the context here poisoned the
      // very next getContext("webgl2") call on the same canvas in Safari,
      // crashing THREE.WebGLRenderer's constructor (getContextAttributes()
      // returns null for a lost context). Letting the browser reclaim
      // abandoned contexts on its own is the safe tradeoff here.
    };
  }, []);

  // Separate from the WebGL setup effect above (which only ever runs once) --
  // this one re-fires whenever the effective accent color changes: the
  // admin's saved/loaded setting, OR a live unsaved preview from the
  // Appearance settings form. Mutates the already-running shader's uniforms
  // directly rather than tearing down and recreating the whole WebGL context.
  useEffect(() => {
    const uniforms = uniformsRef.current;
    if (!uniforms) return;

    if (accentColor) {
      const hueDelta = hexToHueDegrees(accentColor) - hexToHueDegrees(DEFAULT_ACCENT_COLOR);
      uniforms.uHueRotationMatrix.value.copy(buildHueRotationMatrix((hueDelta * Math.PI) / 180));
    } else {
      uniforms.uHueRotationMatrix.value.identity();
    }
  }, [accentColor]);

  // Overrides the gradient's 4 base cosine-gradient colours directly -- on
  // top of whichever set is active, accent color's hue rotation above still
  // applies, same as it does to the hardcoded default.
  useEffect(() => {
    const uniforms = uniformsRef.current;
    if (!uniforms) return;

    const hexes = shaderPalette ?? DEFAULT_SHADER_PALETTE_HEX;
    hexes.forEach((hex, i) => {
      const [r, g, b] = hexToRgbNormalized(hex);
      uniforms.uColourPalette.value[i]!.set(r, g, b);
    });
  }, [shaderPalette]);

  useEffect(() => {
    enabledRef.current = shaderEnabled;
  }, [shaderEnabled]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={`pointer-events-none fixed inset-0 -z-20 h-full w-full ${shaderEnabled ? "" : "hidden"}`}
    />
  );
}
