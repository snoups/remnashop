// Global multiplier for hover/tap "bounce" animations (icon growth, tap scale).
export const BOUNCE_STRENGTH = 0.3;

// Tap scale of the pill behind a tab or segment label -- only the pill grows,
// so the text stays crisp (TabBar, DialogTabs, PillTabs, PeriodPills...).
export const TAP_PILL_SCALE = 1 + 0.05 * BOUNCE_STRENGTH;

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
export function bounceTap(multiplier = 0.05) {
  return {
    whileTap: { scale: 1 + multiplier * BOUNCE_STRENGTH },
  };
}
