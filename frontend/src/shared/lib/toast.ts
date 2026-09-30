import { useSyncExternalStore } from "react";

export type ToastVariant = "error" | "warning" | "success" | "info";

export interface ToastItem {
  id: number;
  variant: ToastVariant;
  message: string;
}

const DISMISS_MS = 5000;
// errors tend to be longer and matter more, so they stay up a bit longer
const ERROR_DISMISS_MS = 8000;

let toasts: ToastItem[] = [];
let nextId = 0;
const listeners = new Set<() => void>();
// per-toast countdown, paused while the pointer is over the toast
const timers = new Map<number, { timeout: ReturnType<typeof setTimeout> | null; remaining: number; startedAt: number }>();

function notify() {
  listeners.forEach((listener) => listener());
}

function push(variant: ToastVariant, message: string) {
  const id = nextId++;
  toasts = [...toasts, { id, variant, message }];
  notify();
  const ms = variant === "error" ? ERROR_DISMISS_MS : DISMISS_MS;
  timers.set(id, { timeout: setTimeout(() => dismissToast(id), ms), remaining: ms, startedAt: Date.now() });
}

export function dismissToast(id: number) {
  const timer = timers.get(id);
  if (timer?.timeout) clearTimeout(timer.timeout);
  timers.delete(id);
  toasts = toasts.filter((item) => item.id !== id);
  notify();
}

export function pauseToast(id: number) {
  const timer = timers.get(id);
  if (!timer?.timeout) return;
  clearTimeout(timer.timeout);
  timer.timeout = null;
  timer.remaining -= Date.now() - timer.startedAt;
}

export function resumeToast(id: number) {
  const timer = timers.get(id);
  if (!timer || timer.timeout) return;
  timer.startedAt = Date.now();
  timer.timeout = setTimeout(() => dismissToast(id), Math.max(timer.remaining, 0));
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
