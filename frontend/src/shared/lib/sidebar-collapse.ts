import { useSyncExternalStore } from "react";

// Per-viewer "icons only" sidebar on desktop; below xl the sidebar is an icon rail regardless.
const STORAGE_KEY = "remnashop_sidebar_collapsed";

const listeners = new Set<() => void>();
let collapsed = localStorage.getItem(STORAGE_KEY) === "1";

export function toggleSidebarCollapsed(): void {
  collapsed = !collapsed;
  localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
  listeners.forEach((listener) => listener());
}

export function useSidebarCollapsed(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => collapsed,
  );
}
