import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@app/App";
import "@shared/i18n";
import { installFormValidationMessages } from "@shared/lib/form-validation";
import { registerServiceWorker } from "@shared/lib/push";
import { readStorage, writeStorage } from "@shared/lib/safe-storage";

import "@app/styles.css";

const CHUNK_RELOAD_KEY = "remnashop_chunk_reload_at";
// a second failure this soon after reloading is a real outage, not a stale tab
const CHUNK_RELOAD_COOLDOWN_MS = 10_000;

// A tab opened before a deploy asks for old hashed chunks that no longer
// exist; a reload picks up the new index.html instead of the route's errorElement.
window.addEventListener("vite:preloadError", (event) => {
  const lastReload = Number(readStorage(CHUNK_RELOAD_KEY, "session"));
  if (Date.now() - lastReload < CHUNK_RELOAD_COOLDOWN_MS) return;
  writeStorage(CHUNK_RELOAD_KEY, String(Date.now()), "session");
  event.preventDefault();
  window.location.reload();
});

// Overlay scrollbars (Firefox and macOS defaults) take no room and scrollbar-gutter does nothing for
// them, so paddings and masks that give the scrollbar's width back must subtract zero.
const scrollbarProbe = document.createElement("div");
scrollbarProbe.style.cssText = "position:absolute;visibility:hidden;width:100px;height:100px;overflow:scroll";
document.body.append(scrollbarProbe);
if (scrollbarProbe.offsetWidth === scrollbarProbe.clientWidth) {
  document.documentElement.style.setProperty("--scrollbar-size", "0px");
}
scrollbarProbe.remove();

installFormValidationMessages();
registerServiceWorker();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
