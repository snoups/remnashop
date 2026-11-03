import { useSyncExternalStore } from "react";

import { readStorage, writeStorage } from "@shared/lib/safe-storage";

export type ApiFailureMode = "off" | "network" | "server";

export type LatencyMode = 0 | 2000 | 10000;

export interface DebugState {
  barVisible: boolean;
  barCollapsed: boolean;
  apiFailure: ApiFailureMode;
  latency: LatencyMode;
  noPermissions: boolean;
  fakeUpdate: boolean;
  fakeOfficialBuild: boolean;
  missingKeys: boolean;
}

// Debug-bar switches, per browser; nothing reaches the backend. The bar opens
// on a long press of the sidebar version pill (desktop only).
const STORAGE_KEY = "remnashop_debug";

const DEFAULT_STATE: DebugState = {
  barVisible: false,
  barCollapsed: false,
  apiFailure: "off",
  latency: 0,
  noPermissions: false,
  fakeUpdate: false,
  fakeOfficialBuild: false,
  missingKeys: false,
};

const listeners = new Set<() => void>();

function load(): DebugState {
  try {
    const stored = JSON.parse(readStorage(STORAGE_KEY) ?? "") as Partial<DebugState>;
    return { ...DEFAULT_STATE, ...stored };
  } catch {
    return DEFAULT_STATE;
  }
}

let state = load();

export function getDebugState(): DebugState {
  return state;
}

export function setDebugState(patch: Partial<DebugState>): void {
  state = { ...state, ...patch };
  writeStorage(STORAGE_KEY, JSON.stringify(state));
  listeners.forEach((listener) => listener());
}

export function toggleDebugBar(): void {
  if (window.matchMedia("(width < 768px)").matches) return;
  setDebugState({ barVisible: !state.barVisible });
}

export function useDebugState(): DebugState {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getDebugState,
  );
}
