// Touching localStorage/sessionStorage throws a SecurityError when the browser
// blocks site data -- at import time that would take the whole bundle down
// before React mounts. Every read and write goes through here instead; a blocked
// store just means nothing is remembered between reloads.
type StorageKind = "local" | "session";

function storageOf(kind: StorageKind): Storage {
  return kind === "local" ? window.localStorage : window.sessionStorage;
}

export function readStorage(key: string, kind: StorageKind = "local"): string | null {
  try {
    return storageOf(kind).getItem(key);
  } catch {
    return null;
  }
}

export function writeStorage(key: string, value: string, kind: StorageKind = "local"): void {
  try {
    storageOf(kind).setItem(key, value);
  } catch {
    // blocked or full: the setting just isn't remembered
  }
}

export function removeStorage(key: string, kind: StorageKind = "local"): void {
  try {
    storageOf(kind).removeItem(key);
  } catch {
    // blocked: nothing was stored to begin with
  }
}
