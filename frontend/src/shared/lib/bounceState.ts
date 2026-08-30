import { useSyncExternalStore } from "react";

// Global multiplier for hover/tap "bounce" animations (icon growth, tap
// scale) — tweaked live via DebugPanel (dev-only).
export const DEFAULT_BOUNCE_STRENGTH = 0.3;

const listeners = new Set<() => void>();
let strength = DEFAULT_BOUNCE_STRENGTH;

export function setBounceStrength(value: number): void {
  strength = value;
  listeners.forEach((listener) => listener());
}

export function useBounceStrength(): number {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => strength,
  );
}

// `whileTap`/`transition` pair shared by every bounce-on-tap element. Plain
// function, not a hook — some call sites are inside .map().
export function bounceTap(bounceStrength: number, multiplier = 0.05) {
  return {
    whileTap: { scale: 1 + multiplier * bounceStrength },
    transition: { type: "spring" as const, stiffness: 500, damping: 15 },
  };
}
