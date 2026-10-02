import { useEffect, useRef } from "react";

import { buildHueRotationMatrix, DEFAULT_TIME_SCALE, PALETTE, type ShaderUniforms } from "@app/shaderState";
import { DEFAULT_ACCENT_COLOR, DEFAULT_SHADER_PALETTE_HEX, hexToHueDegrees, hexToRgbNormalized } from "@shared/lib/color";
import {
  useEffectiveAccentColor,
  useEffectiveShaderEnabled,
  useEffectiveShaderPalette,
} from "@entities/appearance/use-appearance";

const MIN_FRAME_INTERVAL_MS = 1000 / 30;
const BUFFER_SCALE = 0.5;
// No input for this long and the animation eases to a stop, freeing the GPU
const IDLE_TIMEOUT_MS = 30_000;
const EASE_DURATION_MS = 2_000;
const ACTIVITY_EVENTS = ["pointermove", "pointerdown", "keydown", "wheel", "touchstart", "scroll"] as const;

// One oversized triangle covering the viewport, generated from gl_VertexID -- no vertex buffer.
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

function compileProgram(gl: WebGL2RenderingContext): WebGLProgram | null {
  const program = gl.createProgram();
  for (const [type, source] of [
    [gl.VERTEX_SHADER, VERTEX_SHADER],
    [gl.FRAGMENT_SHADER, FRAGMENT_SHADER],
  ] as const) {
    const shader = gl.createShader(type)!;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    gl.attachShader(program, shader);
    gl.deleteShader(shader); // flagged only -- freed together with the program
  }
  gl.linkProgram(program);
  if (gl.getProgramParameter(program, gl.LINK_STATUS)) return program;
  console.error("ShaderBackground: shader link failed", gl.getProgramInfoLog(program));
  gl.deleteProgram(program);
  return null;
}

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
    const program = compileProgram(gl);
    if (!program) return;
    // `gl` narrowing doesn't survive into the closures below
    const context = gl;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Half a CSS pixel per buffer pixel, upscaled by the browser: every fragment
    // costs 4 snoise() calls (~400 ALU ops), and a low-frequency gradient that
    // sits under a backdrop-blur has no detail to lose at quarter density.
    const resize = () => {
      canvas.width = Math.ceil(window.innerWidth * BUFFER_SCALE);
      canvas.height = Math.ceil(window.innerHeight * BUFFER_SCALE);
      context.viewport(0, 0, canvas.width, canvas.height);
    };
    resize();

    const uniforms: ShaderUniforms = {
      uTime: { value: 0 },
      uTimeSin: { value: 0 },
      uScrollProgress: { value: 0 },
      uOpacity: { value: PALETTE.opacity },
      uColourPalette: { value: Float32Array.from(PALETTE.colours) },
      uUvScale: { value: 1 },
      uUvDistortionIterations: { value: 3 },
      uUvDistortionIntensity: { value: 0.15 },
      uHueRotationMatrix: { value: buildHueRotationMatrix(0) },
    };
    const location = (name: string) => context.getUniformLocation(program, name);
    const locations = {
      uTime: location("uTime"),
      uTimeSin: location("uTimeSin"),
      uScrollProgress: location("uScrollProgress"),
      uOpacity: location("uOpacity"),
      uColourPalette: location("uColourPalette"),
      uUvScale: location("uUvScale"),
      uUvDistortionIterations: location("uUvDistortionIterations"),
      uUvDistortionIntensity: location("uUvDistortionIntensity"),
      uHueRotationMatrix: location("uHueRotationMatrix"),
    };
    context.useProgram(program);

    uniformsRef.current = uniforms;

    // Re-uploaded every frame so outside writes to `uniforms` (the effects below) apply on the next draw.
    function renderFrame() {
      context.uniform1f(locations.uTime, uniforms.uTime.value);
      context.uniform1f(locations.uTimeSin, uniforms.uTimeSin.value);
      context.uniform1f(locations.uScrollProgress, uniforms.uScrollProgress.value);
      context.uniform1f(locations.uOpacity, uniforms.uOpacity.value);
      context.uniform3fv(locations.uColourPalette, uniforms.uColourPalette.value);
      context.uniform1f(locations.uUvScale, uniforms.uUvScale.value);
      context.uniform1f(locations.uUvDistortionIterations, uniforms.uUvDistortionIterations.value);
      context.uniform1f(locations.uUvDistortionIntensity, uniforms.uUvDistortionIntensity.value);
      context.uniformMatrix3fv(locations.uHueRotationMatrix, true, uniforms.uHueRotationMatrix.value);
      context.drawArrays(context.TRIANGLES, 0, 3);
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
      stop();
      // `canvas` is a captured const guaranteed non-null by the early return above,
      // but TS doesn't retain that narrowing across a nested function's closure.
      canvas!.style.display = "none";
    }
    canvas.addEventListener("webglcontextlost", onContextLost, false);

    // Time is accumulated per frame rather than derived from a start timestamp,
    // so pauses (blur, idle) and the idle ease both keep uTime continuous.
    let elapsed = 0;
    let lastTick = performance.now();
    let lastDraw = 0;
    let lastActivity = lastTick;
    // 0..1 multiplier on animation speed, eased toward 0 while idle
    let motion = 1;
    let running = false;

    function render() {
      const now = performance.now();
      if (running) {
        frame = requestAnimationFrame(render);
      }
      // rAF runs at display refresh — 120Hz on ProMotion — while
      // DEFAULT_TIME_SCALE makes the motion slow enough that 30fps is
      // indistinguishable from it.
      if (now - lastDraw < MIN_FRAME_INTERVAL_MS) return;
      lastDraw = now;
      const dt = now - lastTick;
      lastTick = now;

      const idle = now - lastActivity > IDLE_TIMEOUT_MS;
      motion = Math.min(1, Math.max(0, motion + (idle ? -dt : dt) / EASE_DURATION_MS));
      const eased = motion * motion * (3 - 2 * motion);
      elapsed += (dt / 1000) * DEFAULT_TIME_SCALE * eased;

      uniforms.uTime.value = elapsed;
      // Same reason the hue matrix is precomputed in shaderState.ts: one value
      // per frame, not per fragment.
      uniforms.uTimeSin.value = Math.sin(uniforms.uTime.value);
      if (enabledRef.current) renderFrame();
      if (idle && motion === 0) stop();
    }

    function start() {
      if (running || context.isContextLost()) return;
      running = true;
      lastTick = performance.now();
      render();
    }

    function stop() {
      running = false;
      cancelAnimationFrame(frame);
    }

    function onActivity() {
      lastActivity = performance.now();
      start();
    }

    if (reduceMotion) {
      render();
    } else {
      start();
      // rAF only stops on its own when the tab is hidden, not when the window
      // merely loses focus -- a dashboard sitting on a second monitor keeps
      // paying full GPU cost.
      window.addEventListener("blur", stop);
      window.addEventListener("focus", onActivity);
      for (const event of ACTIVITY_EVENTS) window.addEventListener(event, onActivity, { passive: true });
    }

    return () => {
      uniformsRef.current = null;
      stop();
      window.removeEventListener("blur", stop);
      window.removeEventListener("focus", onActivity);
      for (const event of ACTIVITY_EVENTS) window.removeEventListener(event, onActivity);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onScroll);
      canvas.removeEventListener("webglcontextlost", onContextLost);
      context.deleteProgram(program);
      // Deliberately NOT calling gl.getExtension("WEBGL_lose_context")?.loseContext()
      // here: it seemed like the correct cleanup, but this
      // canvas element is reused across remounts -- both React StrictMode's
      // deliberate dev-only mount/cleanup/remount dance on first render, and
      // Vite HMR/Fast Refresh. Force-losing the context here poisoned the
      // very next getContext("webgl2") call on the same canvas in Safari
      // (getContextAttributes() returns null for a lost context). Letting the browser reclaim
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

    const hueDelta = accentColor ? hexToHueDegrees(accentColor) - hexToHueDegrees(DEFAULT_ACCENT_COLOR) : 0;
    uniforms.uHueRotationMatrix.value.set(buildHueRotationMatrix((hueDelta * Math.PI) / 180));
  }, [accentColor]);

  // Overrides the gradient's 4 base cosine-gradient colours directly -- on
  // top of whichever set is active, accent color's hue rotation above still
  // applies, same as it does to the hardcoded default.
  useEffect(() => {
    const uniforms = uniformsRef.current;
    if (!uniforms) return;

    const hexes = shaderPalette ?? DEFAULT_SHADER_PALETTE_HEX;
    hexes.forEach((hex, i) => uniforms.uColourPalette.value.set(hexToRgbNormalized(hex), i * 3));
  }, [shaderPalette]);

  useEffect(() => {
    enabledRef.current = shaderEnabled;
  }, [shaderEnabled]);

  return (
    <canvas
      ref={canvasRef}
      className={`pointer-events-none fixed inset-0 -z-20 h-full w-full ${shaderEnabled ? "" : "hidden"}`}
    />
  );
}
