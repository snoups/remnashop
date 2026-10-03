import { useSyncExternalStore } from "react";

import { readStorage, writeStorage } from "@shared/lib/safe-storage";

// Per-browser switch for the background shader, separate from the admin-wide
// shader_enabled setting; nothing goes to the backend.
const STORAGE_KEY = "remnashop_shader_muted";

const listeners = new Set<() => void>();
let muted = readStorage(STORAGE_KEY) === "1";

export function toggleShaderMuted(): void {
  muted = !muted;
  writeStorage(STORAGE_KEY, muted ? "1" : "0");
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
