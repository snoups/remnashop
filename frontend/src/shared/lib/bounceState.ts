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

// `whileTap` prop shared by every bounce-on-tap element. Plain function, not
// a hook — some call sites are inside .map().
//
// No explicit `transition` -- Motion's default spring for this is well-damped
// and settles in one smooth move. The `{ stiffness: 500, damping: 15 }` this
// used to carry was markedly underdamped (critical damping at that stiffness
// is ~45): it overshot and oscillated before settling, and animating a
// `scale` transform through several direction changes made small text/icons
// visibly judder as the browser re-hinted them each reversal. Letting Motion
// pick removed the judder app-wide; see LanguagePicker.tsx's git history for
// how this was diagnosed on one button before generalizing the fix here.
export function bounceTap(bounceStrength: number, multiplier = 0.05) {
  return {
    whileTap: { scale: 1 + multiplier * bounceStrength },
  };
}
