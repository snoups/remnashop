import { useSyncExternalStore } from "react";

// Per-viewer "turn the background shader off right now" switch, independent of
// the admin-wide shader_enabled appearance setting -- nothing is sent to the
// backend, it only persists for this browser.
const STORAGE_KEY = "remnashop_shader_muted";

const listeners = new Set<() => void>();
let muted = localStorage.getItem(STORAGE_KEY) === "1";

export function toggleShaderMuted(): void {
  muted = !muted;
  localStorage.setItem(STORAGE_KEY, muted ? "1" : "0");
  listeners.forEach((listener) => listener());
}

export function useShaderMuted(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => muted,
  );
}
