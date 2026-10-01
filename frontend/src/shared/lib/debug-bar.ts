import { useSyncExternalStore } from "react";

export type ApiFailureMode = "off" | "network" | "server";

export type LatencyMode = 0 | 2000 | 10000;

export interface DebugState {
  barVisible: boolean;
  barCollapsed: boolean;
  apiFailure: ApiFailureMode;
  latency: LatencyMode;
  noPermissions: boolean;
  fakeUpdate: boolean;
  missingKeys: boolean;
}

// Debug-bar switches, per browser -- nothing here reaches the backend. The bar
// itself is hidden behind a long press on the sidebar version pill (desktop only).
const STORAGE_KEY = "remnashop_debug";

const DEFAULT_STATE: DebugState = {
  barVisible: false,
  barCollapsed: false,
  apiFailure: "off",
  latency: 0,
  noPermissions: false,
  fakeUpdate: false,
  missingKeys: false,
};

const listeners = new Set<() => void>();

function load(): DebugState {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "") as Partial<DebugState>;
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
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  listeners.forEach((listener) => listener());
}

export function toggleDebugBar(): void {
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
