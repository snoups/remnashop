// overflow is clipped only while the height animates; left on, it would cut
// off the rows' tap bounce once the section is open
export const COLLAPSE_MOTION = {
  initial: { height: 0, opacity: 0, overflow: "hidden" },
  animate: { height: "auto", opacity: 1, transitionEnd: { overflow: "visible" } },
  exit: { height: 0, opacity: 0, overflow: "hidden" },
  transition: { duration: 0.2, ease: "easeOut" },
} as const;
