import type { ReactNode } from "react";
import { createPortal } from "react-dom";

// `main`'s scroll-fade `mask-image` makes it a containing block for
// `position: fixed`, so a dialog inside it would dim only `main`, not the
// header. `#dialog-root` sits next to `main` inside the `backdrop-blur`
// wrapper, so the backdrop covers the whole panel. Falls back to
// `document.body` outside DashboardLayout.
export function DialogPortal({ children }: { children: ReactNode }) {
  const target = document.getElementById("dialog-root") ?? document.body;
  return createPortal(children, target);
}
