import { useSyncExternalStore } from "react";

export type ToastVariant = "error" | "warning" | "success" | "info";

export interface ToastItem {
  id: number;
  variant: ToastVariant;
  message: string;
}

const DISMISS_MS = 5000;

let toasts: ToastItem[] = [];
let nextId = 0;
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((listener) => listener());
}

function push(variant: ToastVariant, message: string) {
  const id = nextId++;
  toasts = [...toasts, { id, variant, message }];
  notify();
  setTimeout(() => dismissToast(id), DISMISS_MS);
}

export function dismissToast(id: number) {
  toasts = toasts.filter((item) => item.id !== id);
  notify();
}

export const toast = {
  error: (message: string) => push("error", message),
  warning: (message: string) => push("warning", message),
  success: (message: string) => push("success", message),
  info: (message: string) => push("info", message),
};

export function useToasts(): ToastItem[] {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => toasts,
  );
}
