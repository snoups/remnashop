// Glass controls (backdrop-filter) ignore their scroller's scroll-fade mask, so each one carries
// its own (app/styles.css): this keeps --fade-top/--fade-bottom at the scroller's top and bottom
// edges in the control's coordinates.

const SCROLLERS = ".scroll-fade-top, .scroll-fade-y";
const GLASS = '[class*="backdrop-blur"]:not(.sticky)';

function update(): void {
  for (const scroller of document.querySelectorAll<HTMLElement>(SCROLLERS)) {
    const edges = scroller.getBoundingClientRect();
    for (const glass of scroller.querySelectorAll<HTMLElement>(GLASS)) {
      const box = glass.getBoundingClientRect();
      glass.style.setProperty("--fade-top", `${edges.top - box.top}px`);
      glass.style.setProperty("--fade-bottom", `${edges.bottom - box.top}px`);
    }
  }
}

export function installGlassFade(): void {
  let frame = 0;
  const schedule = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      update();
    });
  };
  // capture: scroll doesn't bubble, and any nested scroller can move a control
  document.addEventListener("scroll", schedule, { capture: true, passive: true });
  window.addEventListener("resize", schedule);
  // pages and dialogs mounting, lists loading, panels expanding
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
}
