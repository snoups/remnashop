import { useEffect, useRef } from "react";

import { buildHueRotationMatrix, DEFAULT_TIME_SCALE, PALETTE, type ShaderUniforms } from "@app/shader-state";
import { compileShaderGradient } from "@shared/lib/shader-gradient";
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
// Safari drops the context on sleep/wake, GPU switches and memory pressure; past this many losses the canvas is hidden for good
const MAX_CONTEXT_LOSSES = 5;

/** App-wide noise-gradient background on one full-viewport canvas, mounted once at the app root. */
export function ShaderBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const uniformsRef = useRef<ShaderUniforms | null>(null);
  const loopRef = useRef<{ resume: () => void; stop: () => void } | null>(null);
  // read by the render loop: skips drawing without recreating the WebGL context
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
    // Safari hands out an already-lost context once it has blocked WebGL for the site
    if (!gl || gl.isContextLost()) return;
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

    let program: WebGLProgram | null = null;
    let locations = {} as Record<keyof ShaderUniforms, WebGLUniformLocation | null>;
    // Every GL object dies with the context, so a restored one needs all of this again.
    function setup(): boolean {
      program = compileShaderGradient(context);
      if (!program) return false;
      for (const name of Object.keys(uniforms) as (keyof ShaderUniforms)[]) {
        locations[name] = context.getUniformLocation(program, name);
      }
      context.useProgram(program);
      resize();
      return true;
    }
    if (!setup()) return;

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
    let timer = 0;

    let contextLosses = 0;

    function hideForGood() {
      stop();
      canvas!.style.display = "none";
    }

    function onContextLost(event: Event) {
      stop();
      // preventDefault() is what asks the browser for a webglcontextrestored
      if (++contextLosses > MAX_CONTEXT_LOSSES) return hideForGood();
      event.preventDefault();
    }

    function onContextRestored() {
      if (!setup()) return hideForGood();
      renderFrame();
      if (!reduceMotion && document.hasFocus()) start();
    }
    canvas.addEventListener("webglcontextlost", onContextLost, false);
    canvas.addEventListener("webglcontextrestored", onContextRestored, false);

    // Time is accumulated per frame rather than derived from a start timestamp,
    // so pauses (blur, idle) and the idle ease both keep uTime continuous.
    let elapsed = 0;
    let lastTick = performance.now();
    let lastActivity = lastTick;
    // 0..1 multiplier on animation speed, eased toward 0 while idle
    let motion = 1;
    let running = false;

    function render() {
      const now = performance.now();
      // A plain rAF chain would wake the renderer at display refresh (120Hz on
      // ProMotion) only to skip most frames; the motion is slow enough that 30fps
      // looks the same. rAF still aligns the draw to vsync and pauses in hidden tabs.
      if (running) {
        timer = window.setTimeout(() => {
          frame = requestAnimationFrame(render);
        }, MIN_FRAME_INTERVAL_MS);
      }
      const dt = now - lastTick;
      lastTick = now;

      const idle = now - lastActivity > IDLE_TIMEOUT_MS;
      motion = Math.min(1, Math.max(0, motion + (idle ? -dt : dt) / EASE_DURATION_MS));
      const eased = motion * motion * (3 - 2 * motion);
      elapsed += (dt / 1000) * DEFAULT_TIME_SCALE * eased;

      uniforms.uTime.value = elapsed;
      // Same reason the hue matrix is precomputed in shader-state.ts: one value
      // per frame, not per fragment.
      uniforms.uTimeSin.value = Math.sin(uniforms.uTime.value);
      if (enabledRef.current) renderFrame();
      if (idle && motion === 0) stop();
    }

    function start() {
      if (running || !enabledRef.current || context.isContextLost()) return;
      running = true;
      lastTick = performance.now();
      render();
    }

    function stop() {
      running = false;
      clearTimeout(timer);
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
      // rAF stops only when the tab is hidden, not on blur, so a dashboard on
      // a second monitor would keep the GPU busy
      window.addEventListener("blur", stop);
      window.addEventListener("focus", onActivity);
      for (const event of ACTIVITY_EVENTS) window.addEventListener(event, onActivity, { passive: true });
    }

    loopRef.current = {
      resume() {
        renderFrame();
        if (!reduceMotion) onActivity();
      },
      stop,
    };

    return () => {
      uniformsRef.current = null;
      loopRef.current = null;
      stop();
      window.removeEventListener("blur", stop);
      window.removeEventListener("focus", onActivity);
      for (const event of ACTIVITY_EVENTS) window.removeEventListener(event, onActivity);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onScroll);
      canvas.removeEventListener("webglcontextlost", onContextLost);
      canvas.removeEventListener("webglcontextrestored", onContextRestored);
      context.deleteProgram(program);
      // No WEBGL_lose_context here: the canvas is reused across StrictMode/HMR
      // remounts, and a force-lost context breaks the next getContext() in Safari.
    };
  }, []);

  // saved accent or a live preview; updates the running shader's uniforms in place
  useEffect(() => {
    const uniforms = uniformsRef.current;
    if (!uniforms) return;

    const hueDelta = accentColor ? hexToHueDegrees(accentColor) - hexToHueDegrees(DEFAULT_ACCENT_COLOR) : 0;
    uniforms.uHueRotationMatrix.value.set(buildHueRotationMatrix((hueDelta * Math.PI) / 180));
  }, [accentColor]);

  // the accent's hue rotation still applies on top of a custom palette
  useEffect(() => {
    const uniforms = uniformsRef.current;
    if (!uniforms) return;

    const hexes = shaderPalette ?? DEFAULT_SHADER_PALETTE_HEX;
    hexes.forEach((hex, i) => uniforms.uColourPalette.value.set(hexToRgbNormalized(hex), i * 3));
  }, [shaderPalette]);

  useEffect(() => {
    enabledRef.current = shaderEnabled;
    if (shaderEnabled) loopRef.current?.resume();
    else loopRef.current?.stop();
  }, [shaderEnabled]);

  return (
    <canvas
      ref={canvasRef}
      className={`pointer-events-none fixed inset-0 -z-20 h-full w-full ${shaderEnabled ? "" : "hidden"}`}
    />
  );
}
