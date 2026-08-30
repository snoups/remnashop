import type { ReactNode } from "react";
import { createPortal } from "react-dom";

// `main` (DashboardLayout) has a `mask-image` for its scroll-fade edge,
// which makes it a containing block for `position: fixed` descendants --
// same as `transform`/`filter`/`backdrop-filter`. A dialog nested inside
// `main` would size its `fixed inset-0` backdrop to `main`'s own box
// instead of the viewport, leaving the header undimmed.
//
// `#dialog-root` (DashboardLayout) is a sibling of `main`, still inside the
// panel wrapper that has `backdrop-blur` -- which itself is a containing
// block. Portaling there keeps dialogs escaping `main`'s mask while still
// bounded by the wrapper, so the darkened backdrop covers the whole panel
// (header included), matching the look before the scroll fade existed.
// Falls back to `document.body` if that node isn't mounted (e.g. a dialog
// rendered outside DashboardLayout).
export function DialogPortal({ children }: { children: ReactNode }) {
  const target = document.getElementById("dialog-root") ?? document.body;
  return createPortal(children, target);
}
