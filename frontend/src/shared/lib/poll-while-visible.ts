// Calls `load` every `intervalMs` while the tab is visible, and once right away
// when it becomes visible again; a hidden tab doesn't poll. Returns the cleanup.
export function pollWhileVisible(load: () => void, intervalMs: number): () => void {
  let timer: ReturnType<typeof setInterval> | undefined;
  const start = () => {
    if (timer === undefined) timer = setInterval(load, intervalMs);
  };
  const stop = () => {
    clearInterval(timer);
    timer = undefined;
  };
  const onVisibilityChange = () => {
    if (document.visibilityState === "visible") {
      load();
      start();
    } else {
      stop();
    }
  };
  if (document.visibilityState === "visible") start();
  document.addEventListener("visibilitychange", onVisibilityChange);
  return () => {
    stop();
    document.removeEventListener("visibilitychange", onVisibilityChange);
  };
}
